"""对白生成服务 — 从 LLM 生成幕结构并展开对白。"""

import json
import sys
import re as _re
from difflib import SequenceMatcher

from app.core.llm import chat, chat_json, get_llm_config
from app.core.store import (
    get_project, get_episode, add_dialogue, add_character, update_episode,
)

# ── DialogueGenerator 定义 ──────────────────────────
def _extract_chars_from_story(story_text: str) -> list[str] | None:
    """从故事末尾提取【角色清单】，返回角色名列表或None"""
    import re as _re
    if not story_text:
        return None
    m = _re.search(r'【角色清单】', story_text)
    if not m:
        return None
    tail = story_text[m.end():].strip()
    chars = []
    for line in tail.split('\n'):
        ln = line.strip()
        if not ln:
            continue
        if ln.startswith('【') or ln.startswith('#') or ln.startswith('---'):
            break
        ln = _re.sub(r'^[\d\.\-\s]+', '', ln).strip()
        if ln and '旁白' not in ln:
            chars.append(ln)
    return chars if chars else None


def _build_chars_info(proj: dict, detailed: bool = False) -> list[str]:
    """构建角色信息列表。detailed=True 时包含 base_instruct。"""
    chars = list(proj.get("characters", []))
    result = []
    for c in chars:
        if c.get("name", "").strip() == "旁白":
            continue
        if detailed:
            base_instruct = c.get("base_instruct", "")
            desc = c.get("description", "无")
            result.append(
                f"- {c['name']} (voice: {c.get('voice_id', '默认')}, "
                f"基础风格: {base_instruct or '无'}, "
                f"性格/描述: {desc})"
            )
        else:
            result.append(
                f"- {c['name']} (voice: {c.get('voice_id', '默认')}, "
                f"描述: {c.get('description', '无')})"
            )
    return result


class DialogueGenerator:
    """从 LLM 生成幕结构并逐幕展开对白，通过 yield 返回 SSE 事件。"""

    def __init__(self, project_id: str, episode_id: str, body):
        self.project_id = project_id
        self.episode_id = episode_id
        self.body = body
        self.proj = get_project(project_id)
        self.ep = get_episode(project_id, episode_id)
    def _parse_story_text(self, text: str) -> list[dict]:
        """解析LLM生成的完整故事文本，提取角色名、instruct、text。

        新解析逻辑（多步拼合）：
        1. 按 [角色名] 标记切分段落
        2. 无标记段落 → 作为 [旁白] 条目（连续无标记段落合并）
        3. 有标记段落 → 提取角色名+情绪+text
           - text 优先取英文引号 "" 内的内容
           - 引号外的描述性文字拼合到该角色的 text 里（用换行分隔）
           - 无引号时整体作为 text（向后兼容）

        Args:
            text: LLM生成的完整故事文本

        Returns:
            list of dict: [{"role": "小明", "instruct": "沉声", "text": "..."}, ...]
        """
        import re

        # 按 [标记] 切分段落，保留标记内容
        marker_pattern = re.compile(r'\[([^\]]+)\]')
        markers = list(marker_pattern.finditer(text))

        result = []
        narration_buffer = []  # 用于合并连续无标记段落

        def flush_narration():
            """将累积的旁白缓冲区写入结果"""
            nonlocal narration_buffer
            if narration_buffer:
                merged = "\n".join(narration_buffer).strip()
                if merged:
                    result.append({
                        "role": "旁白",
                        "instruct": "",
                        "text": merged,
                    })
                narration_buffer = []

        if not markers:
            # 整个文本没有任何标记，整体作为旁白
            stripped = text.strip()
            if stripped:
                result.append({"role": "旁白", "instruct": "", "text": stripped})
            return result

        # 处理第一个标记之前的无标记段落
        first_marker_start = markers[0].start()
        if first_marker_start > 0:
            prefix = text[:first_marker_start].strip()
            if prefix:
                narration_buffer.append(prefix)

        for i, marker in enumerate(markers):
            role_name = marker.group(1).strip()
            # 标记之后的内容：从标记结束到下一个标记开始（或文本末尾）
            content_start = marker.end()
            if i + 1 < len(markers):
                content_end = markers[i + 1].start()
            else:
                content_end = len(text)
            raw_content = text[content_start:content_end].strip()

            # 从 raw_content 中提取情绪标注（xxx）和内容
            instruct = ""
            inner_text = raw_content
            # 用 str.find 避免正则引擎 bug
            paren_chars = [('（', '）'), ('(', ')')]
            for left, right in paren_chars:
                if raw_content.startswith(left):
                    end_pos = raw_content.find(right, 1)
                    if end_pos != -1:
                        instruct = raw_content[1:end_pos].strip()
                        inner_text = raw_content[end_pos + 1:].strip()
                        break

            # 提取引号内容 + 引号外描述，拼合成一个完整 text
            quote_iter = list(re.finditer(r'"([^"]*)"', inner_text))
            quoted_parts = [qm.group(1) for qm in quote_iter]

            if quoted_parts:
                # 有引号：引号内容作为角色对话（多引号不拆散）
                # 引号外描述性文字 → 独立旁白
                # 步骤：1) flush开头旁白 2) 添加角色条目(多引号拼合) 3) flush引号后旁白
                flush_narration()

                # 收集引号外描述文字（旁白）
                pre_narration = []
                post_narration = []
                # 第一段引号前的描述
                first_q_start = quote_iter[0].start()
                if first_q_start > 0:
                    before = inner_text[:first_q_start].strip()
                    if before:
                        pre_narration.append(before)
                # 最后一段引号后的描述
                last_q_end = quote_iter[-1].end()
                last_qm = quote_iter[-1]
                # 重新获取最后一个引号后的内容
                after = inner_text[quote_iter[-1].end():].strip()
                if after:
                    post_narration.append(after)

                # 输出引号前旁白
                for nar in pre_narration:
                    result.append({"role": "旁白", "instruct": "", "text": nar})

                # 输出角色条目：每个引号内容单独一条
                for qt in quoted_parts:
                    result.append({
                        "role": role_name,
                        "instruct": instruct,
                        "text": qt,
                    })

                # 输出引号后旁白
                for nar in post_narration:
                    result.append({"role": "旁白", "instruct": "", "text": nar})
            else:
                # 无引号：整体作为 text（向后兼容）
                flush_narration()
                text_content = inner_text
                # 清理markdown代码块
                if text_content.startswith('```'):
                    text_content = re.sub(r'^```\w*\n?', '', text_content)
                    text_content = re.sub(r'\n?```$', '', text_content)
                    text_content = text_content.strip()
                if text_content:
                    result.append({
                        "role": role_name,
                        "instruct": instruct,
                        "text": text_content,
                    })

        # 处理最后一个标记之后的无标记段落
        flush_narration()

        return result

    async def _generate_story(self):
        """一次性生成完整故事文本，解析后入库。yield SSE 事件。"""
        proj = self.proj
        ep = self.ep
        body = self.body

        llm_cfg = get_llm_config()
        if not llm_cfg.get("base_url") or not llm_cfg.get("api_key"):
            yield "error", {"message": "LLM 未配置，请先填写 app/config.yaml 中的 llm.base_url 和 llm.api_key"}
            return

        episode_summary = ep.get("summary", "")
        if not episode_summary:
            yield "error", {"message": "该剧集没有摘要，请先生成或填写摘要"}
            return

        chars_info = _build_chars_info(proj, detailed=True)

        # T3: 上下文注入 — 前情（第1集~第N-1集）
        prev_summaries = []
        for prev_ep in proj.get("episodes", []):
            if prev_ep["id"] == self.episode_id:
                break
            if prev_ep.get("summary"):
                prev_summaries.append(f"《{prev_ep['title']}》: {prev_ep['summary']}")

        # T3: 后续（第N+1~第N+5集，最多5章）
        all_eps = proj.get("episodes", [])
        ep_index = next((i for i, e in enumerate(all_eps) if e["id"] == self.episode_id), 0)
        next_summaries = []
        for i in range(ep_index + 1, min(ep_index + 6, len(all_eps))):
            ne = all_eps[i]
            if ne.get("summary"):
                next_summaries.append(f"《{ne['title']}》: {ne['summary']}")

        # T4: 可配置参数
        target_duration_min = getattr(body, 'target_duration_min', 25)
        narration_ratio = getattr(body, 'narration_ratio', 20)
        style = getattr(body, 'style', '')
        temperature = getattr(body, 'temperature', 0.7)
        word_count = int(target_duration_min * 260)

        style_prompt = f"\n【风格要求】\n{style}" if style else ""

        # T4: 构建 prompt
        system = f"""你是一个有声故事编剧。根据摘要生成一个完整的故事。
总字数约{word_count}字（允许±20%浮动）。
旁白约占{narration_ratio}%。
{style_prompt}

【对话格式】
- 角色对话必须用『』引号包裹，例如：黎维：『数据已上传，所有人都能看到真相。』
- 旁白不需要引号，直接叙述即可
- 『』只用于包裹角色对话，禁止用于标注特殊名词、强调词语或其他用途

【角色清单】
- 请在故事末尾空一行，单独列出【角色清单】，列出所有在故事中出现过的角色名
- 每行一个角色名，不要序号，不含"旁白"
注意：这部分是生成角色清单，不是让角色说话，不要打乱故事的结构和节奏。

【衔接要求】
- 本章内容必须承前启后，与前后章节自然衔接
- 如果有后续章节，本章不能提前消耗后续的关键情节或悬念
- 如果没有后续章节（最终章），本章必须完整收尾，给出结局

输出纯文本，不要JSON，不要解释。"""

        user = f"标题：{ep['title']}\n摘要：{episode_summary}\n"
        if chars_info:
            user += "角色信息（性格+朗读风格，角色行为需符合其性格）：\n"
            for c in chars_info:
                user += f"  {c}\n"
        if prev_summaries:
            user += f"\n【前情】\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(prev_summaries)) + "\n"
        if next_summaries:
            user += f"\n【后续章节摘要（请勿提前消耗其关键情节）】\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(next_summaries)) + "\n"
        else:
            user += "\n【后续】无（本章为最终章）\n"
        if getattr(body, 'instruction', ''):
            user += f"\n额外要求：{body.instruction}\n"
        user += f"\n请生成约{word_count}字的完整故事。"

        yield "generating", {"word_count": word_count, "narration_ratio": narration_ratio, "style": style}

        # 调用 LLM（用 chat_json，因为底层用的是 openai chat，返回纯文本）
        sys.stderr.write(f"  [B2-STORY] word_count={word_count}, temp={temperature}\n")
        sys.stderr.flush()

        try:
            story_text = await chat([
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ], max_tokens=max(4096, word_count * 3), timeout=600, temperature=temperature)
        except Exception as e:
            yield "error", {"message": f"LLM 故事生成失败: {e}"}
            return

        if not story_text or not story_text.strip():
            yield "error", {"message": "LLM 返回空故事文本"}
            return

        # 清理标题行（# 标题）和多余空行
        story_text = _re.sub(r'^#\s+.*\n', '', story_text)
        story_text = _re.sub(r'\n{3,}', '\n\n', story_text)
        story_text = story_text.strip()

        sys.stderr.write(f"  [B2-STORY] raw text length={len(story_text)}\\n")
        sys.stderr.flush()

        # T3: 保存 raw_text 到 episode（在解析之前保存原始文本）
        update_episode(self.project_id, self.episode_id, raw_text=story_text)
        # 同步更新 self.ep 中的 raw_text，避免后续使用旧缓存
        self.ep["raw_text"] = story_text

        # T1: 清除旧对白，避免重复叠加
        from app.core import store
        async with store.atomic_update() as data:
            for p in data["projects"]:
                if p["id"] == self.project_id:
                    for ep_in in p["episodes"]:
                        if ep_in["id"] == self.episode_id:
                            ep_in["dialogues"] = []
                            break
                    break

# T1: 调用直接LLM拆解法
        from app.core.dialogue_parser import parse_story_direct

        raw_chars = _extract_chars_from_story(story_text)
        if raw_chars:
            sys.stderr.write(f"  [B2-PARSE] 从故事提取角色清单: {raw_chars}\n")
        base_chars = raw_chars or [c.split(" (")[0].lstrip("- ") for c in chars_info if "旁白" not in c] if chars_info else []

        # 传完整 api_url
        api_url = llm_cfg.get("base_url", "").rstrip("/") + "/chat/completions"

        dialogues = parse_story_direct(
            story_text,
            known_chars=base_chars,
            llm_cfg={"api_url": api_url, "api_key": llm_cfg.get("api_key"), "model": llm_cfg.get("model")}
        )

        if not dialogues:
            yield "error", {"message": "无法解析故事文本，请检查输出格式"}
            return

        yield "story_parsed", {"total_segments": len(dialogues)}

        # T5: 角色匹配入库
        created = []
        new_chars = []
        new_char_cache: dict = {}

        for idx, item in enumerate(dialogues):
            char_name = item["role"]
            instruct = item["instruct"]
            text = item["text"]

            char_id, is_new = self._resolve_char_id(char_name, new_char_cache)
            if is_new:
                new_chars.append(char_name)

            if char_id:
                dlg = add_dialogue(self.project_id, self.episode_id, char_id, text, idx, instruct)
                if dlg:
                    created.append(dlg["id"])
                    yield "progress", {"current": len(created), "total": len(dialogues)}

        # 角色重复校验（复用原有逻辑）
        if new_chars:
            existing_norm_map = {}
            for c in proj.get("characters", []):
                if c["name"] not in new_chars:
                    n = _re.sub(r'[\s，。、；：！？""''（）【】《》\-·—_]', '', c["name"]).lower()
                    if n:
                        existing_norm_map[n] = c["id"]
            chars_to_remove = []
            id_remap = {}
            for nc_name in list(new_chars):
                nc_norm = _re.sub(r'[\s，。、；：！？""''（）【】《》\-·—_]', '', nc_name).lower()
                if nc_norm in existing_norm_map:
                    new_cid = new_char_cache.get(nc_name, "")
                    existing_cid = existing_norm_map[nc_norm]
                    if new_cid and existing_cid and new_cid != existing_cid:
                        id_remap[new_cid] = existing_cid
                    chars_to_remove.append(nc_name)
            if id_remap:
                from app.core import store
                async with store.atomic_update() as data:
                    for p in data["projects"]:
                        if p["id"] == self.project_id:
                            for ep_in in p["episodes"]:
                                if ep_in["id"] == self.episode_id:
                                    for d in ep_in["dialogues"]:
                                        if d.get("character_id") in id_remap:
                                            d["character_id"] = id_remap[d["character_id"]]
                                    break
                            p["characters"] = [c for c in p["characters"] if c["name"] not in chars_to_remove]
                            break
                proj["characters"] = [c for c in proj["characters"] if c["name"] not in chars_to_remove]
                new_chars = [n for n in new_chars if n not in chars_to_remove]

        if new_chars:
            yield "new_characters", {"names": new_chars}

        yield "complete", {
            "created": len(created),
            "dialogue_ids": created,
            "new_characters": new_chars,
            "_debug": {
                "word_count": word_count,
                "parsed_segments": len(dialogues),
                "actual": len(created),
            },
        }


    def _resolve_char_id(self, char_name: str, new_char_cache: dict) -> tuple:
        """解析角色名到 character_id。返回 (char_id, is_new)。"""
        proj = self.proj
        # 1. 精确匹配已有角色
        for c in proj.get("characters", []):
            if c["name"].strip() == char_name:
                return c["id"], False
        # 2. 本次已创建
        if char_name in new_char_cache:
            return new_char_cache[char_name], False
        # 3. 归一化匹配 + 互相包含
        norm = _re.sub(r'[\s，。、；：！？""''（）【】《》\-·—_]', '', char_name)
        for c in proj.get("characters", []):
            c_norm = _re.sub(r'[\s，。、；：！？""''（）【】《》\-·—_]', '', c["name"])
            if c_norm == norm:
                return c["id"], False
        for c in proj.get("characters", []):
            c_norm = _re.sub(r'[\s，。、；：！？""''（）【】《》\-·—_]', '', c["name"])
            if norm and c_norm and (norm in c_norm or c_norm in norm):
                return c["id"], False
        # 4. 模糊匹配 SequenceMatcher
        best_ratio = 0.0
        best_cid = ""
        for c in proj.get("characters", []):
            c_norm = _re.sub(r'[\s，。、；：！？""''（）【】《》\-·—_]', '', c["name"])
            if not c_norm or not norm:
                continue
            ratio = SequenceMatcher(None, norm, c_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_cid = c["id"]
        if best_ratio >= 0.7 and best_cid:
            return best_cid, False
        # 5. 创建新角色
        existing_voices = [c.get("voice_id", "") for c in proj.get("characters", [])]
        voice_id = existing_voices[0] if existing_voices else ""
        new_char = add_character(
            self.project_id, char_name, voice_id,
            description=f"AI 自动生成角色: {char_name}"
        )
        if new_char:
            new_char_cache[char_name] = new_char["id"]
            proj["characters"].append(new_char)
            return new_char["id"], True
        return "", False

    async def generate(self):
        """异步生成器，yield (event_type, data_dict) 元组。"""
        proj = self.proj
        ep = self.ep
        body = self.body

        llm_cfg = get_llm_config()
        if not llm_cfg.get("base_url") or not llm_cfg.get("api_key"):
            yield "error", {"message": "LLM 未配置，请先填写 app/config.yaml 中的 llm.base_url 和 llm.api_key"}
            return

        episode_summary = ep.get("summary", "")
        if not episode_summary:
            yield "error", {"message": "该剧集没有摘要，请先生成或填写摘要"}
            return

        chars_info = _build_chars_info(proj, detailed=True)

        # 上下文：前面所有剧集的摘要
        prev_summaries = []
        for prev_ep in proj.get("episodes", []):
            if prev_ep["id"] == self.episode_id:
                break
            if prev_ep.get("summary"):
                prev_summaries.append(f"《{prev_ep['title']}》: {prev_ep['summary']}")

        # 本集在整体故事中的位置
        all_eps = proj.get("episodes", [])
        ep_index = next((i for i, e in enumerate(all_eps) if e["id"] == self.episode_id), 0)
        total_eps = len(all_eps)
        if total_eps > 1:
            if ep_index == 0:
                position_hint = "这是第一集，需要建立角色关系和故事背景。"
            elif ep_index == total_eps - 1:
                position_hint = "这是最后一集，需要收束所有线索，给出结局。"
            elif ep_index < total_eps // 3:
                position_hint = "故事处于铺垫阶段，角色关系正在建立。"
            elif ep_index < total_eps * 2 // 3:
                position_hint = "故事处于发展阶段，冲突正在升级。"
            else:
                position_hint = "故事接近高潮，矛盾即将爆发。"
        else:
            position_hint = "这是唯一一集，需要在有限空间内讲完整个故事。"

        # ── 阶段 1：规划幕结构 ──
        target_total = max(10, body.target_duration_min * 60 // 4)
        num_scenes = max(3, min(8, target_total // 40))

        plan_system = (
            f"你是一个有声故事编剧。根据给定摘要，将故事划分为若干幕（scene），输出 JSON。\n\n"
            f"输出格式：\n"
            f'{{"scenes":[{{"summary":"本幕概述（50字内）","type":"narration|dialogue|mixed","lines":条数}}, ...]}}\n\n'
            f"要求：\n"
            f"- 共 {num_scenes} 幕，每幕有明确的叙事功能（铺垫/冲突/转折/高潮/收尾等）\n"
            f"- 总条数约 {target_total} 条，旁白比例约 {body.narration_ratio}%\n"
            f"- type 说明：narration=旁白为主，dialogue=对话为主，mixed=混合\n"
            f"- 各幕条数之和必须等于 {target_total}\n"
            f"- 角色的行为、对话风格、情感反应必须符合其性格特征和基础风格"
        )

        plan_user = f"标题：{ep['title']}\n摘要：{episode_summary}\n"
        if chars_info:
            plan_user += "角色信息（性格+朗读风格，角色行为需符合其性格）：\n"
            for c in chars_info:
                plan_user += f"  {c}\n"
        if prev_summaries:
            plan_user += f"前情：{'；'.join(s[:60] for s in prev_summaries)}\n"
        if body.instruction:
            plan_user += f"额外要求：{body.instruction}\n"
        plan_user += f"请将这个故事划分为 {num_scenes} 幕，输出 JSON。"

        yield "planning", {"scenes": num_scenes, "total": target_total}

        try:
            plan_result = await chat_json([
                {"role": "system", "content": plan_system},
                {"role": "user", "content": plan_user},
            ], max_tokens=4000, timeout=300)
        except Exception as e:
            yield "error", {"message": f"LLM 幕规划失败: {e}"}
            return

        scenes_plan = plan_result.get("scenes", [])
        sys.stderr.write(f"  [PLAN] scenes={len(scenes_plan)}, data={json.dumps(plan_result, ensure_ascii=False)[:300]}\n")
        sys.stderr.flush()
        if not scenes_plan:
            yield "error", {"message": "LLM 未返回幕结构"}
            return

        # ── 阶段 2：逐幕展开生成对白 ──
        all_dialogues_data: list[dict] = []
        completed_scenes_summary: list[str] = []

        for scene_i, scene in enumerate(scenes_plan):
            scene_summary = scene.get("summary", f"第{scene_i + 1}幕")
            scene_type = scene.get("type", "mixed")
            scene_lines = scene.get("lines", 40)
            scene_narr = int(scene_lines * body.narration_ratio / 100)
            scene_dialog = scene_lines - scene_narr

            yield "scene_start", {"index": scene_i, "summary": scene_summary}

            context_tail = ""
            if completed_scenes_summary:
                context_tail = "\n\n【前情提要】:\n" + "\n".join(
                    f"幕{i + 1}: {s}" for i, s in enumerate(completed_scenes_summary)
                )

            scene_collected: list[dict] = []
            existing_scene_lines: list[str] = []

            while len(scene_collected) < scene_lines:
                still_need = min(20, scene_lines - len(scene_collected))

                existing_hint = ""
                if existing_scene_lines:
                    existing_hint = "\n\n【本幕已生成的末尾对白，请续写】:\n" + "\n".join(existing_scene_lines[-5:])
                    existing_hint += f"\n（已生成 {len(scene_collected)}/{scene_lines} 条，还需 {still_need} 条）"

                type_desc = (
                    "旁白叙述为主" if scene_type == "narration"
                    else "角色对话为主" if scene_type == "dialogue"
                    else "旁白和对话均衡"
                )
                write_system = (
                    "你是一个有声故事编剧。\n\n"
                    "严格输出 JSON，不要输出任何其他文字（不要解释、不要总结）：\n"
                    '{"dialogues":[{"character":"角色名","text":"对白内容","instruct":"此处场景情绪"}]}\n\n'
                    f"必须生成恰好 {still_need} 条对白，{scene_type} 类型（{type_desc}），"
                    "每条 15-40 字，只用给定角色。\n\n"
                    "【instruct 规则】\n"
                    "- instruct 是此条白在此场景下的情绪/语气提示，会叠加到角色基础风格上\n"
                    "- 格式：直接写情绪词，如'略带紧张'、'低沉'、'温和'、'叙述性'\n"
                    "- 同一角色的 instruct 基调应保持一致，允许小幅变化但不要剧烈跳跃\n"
                    "- 示例：'略带紧张'、'低沉叙述'、'温和'、'平静略带感慨'\n"
                    f"dialogues 数组长度必须等于 {still_need}。"
                )

                write_user = f"故事：{ep['title']}\n本集：{episode_summary}\n"
                write_user += f"第 {scene_i + 1} 幕：{scene_summary}\n"
                if chars_info:
                    write_user += "角色：" + "、".join(c.split(" (")[0] for c in chars_info) + "\n"
                if prev_summaries:
                    write_user += "前情：" + "、".join(s[:30] for s in prev_summaries) + "\n"
                if body.instruction:
                    write_user += f"要求：{body.instruction}\n"
                if context_tail:
                    write_user += context_tail + "\n"
                write_user += existing_hint + f"\n生成 {still_need} 条："

                batch: list = []
                for retry in range(3):
                    try:
                        est_tokens = int(still_need * 120) + 1000
                        scene_result = await chat_json([
                            {"role": "system", "content": write_system},
                            {"role": "user", "content": write_user},
                        ], max_tokens=est_tokens, timeout=300)
                        batch = scene_result.get("dialogues", [])
                    except Exception as e:
                        sys.stderr.write(f"  [scene {scene_i+1}] retry={retry} ERROR: {e}\n")
                        sys.stderr.flush()
                        continue
                    sys.stderr.write(f"  [scene {scene_i+1}] retry={retry} still_need={still_need}, got={len(batch) if batch else 0}, collected={len(scene_collected)}\n")
                    sys.stderr.flush()
                    if batch:
                        break

                if not batch:
                    break

                batch = batch[:still_need]
                scene_collected.extend(batch)
                for b in batch:
                    ch = b.get("character", "?")
                    txt = b.get("text", "")[:30]
                    existing_scene_lines.append(f"{ch}: {txt}")

                if len(batch) < still_need:
                    break

            if scene_collected:
                all_dialogues_data.extend(scene_collected)
                completed_scenes_summary.append(scene_summary)

            yield "scene_done", {"index": scene_i, "count": len(scene_collected)}

        # ── 阶段 3：角色匹配与入库 ──
        dialogues_data = all_dialogues_data
        sys.stderr.write(f"  [RESULT] target={target_total}, scenes={len(scenes_plan)}, actual={len(dialogues_data)}\n")
        sys.stderr.flush()

        created = []
        new_chars = []
        new_char_cache: dict = {}

        for dlg_data in dialogues_data:
            char_name = dlg_data.get("character", "").strip()
            text = dlg_data.get("text", "")
            instruct = dlg_data.get("instruct", "")

            if not text:
                continue

            char_id, is_new = self._resolve_char_id(char_name, new_char_cache)
            if is_new:
                new_chars.append(char_name)

            if char_id:
                dlg = add_dialogue(self.project_id, self.episode_id, char_id, text, len(created), instruct)
                if dlg:
                    created.append(dlg["id"])
                    yield "progress", {"current": len(created), "total": len(dialogues_data)}

        # 事后校验：检查本次新建角色是否与已有角色重复
        if new_chars:
            existing_norm_map = {}
            for c in proj.get("characters", []):
                if c["name"] not in new_chars:
                    n = _re.sub(r'[\s，。、；：！？""''（）【】《》\-·—_]', '', c["name"]).lower()
                    if n:
                        existing_norm_map[n] = c["id"]
            chars_to_remove = []
            id_remap = {}
            for nc_name in list(new_chars):
                nc_norm = _re.sub(r'[\s，。、；：！？""''（）【】《》\-·—_]', '', nc_name).lower()
                if nc_norm in existing_norm_map:
                    new_cid = new_char_cache.get(nc_name, "")
                    existing_cid = existing_norm_map[nc_norm]
                    if new_cid and existing_cid and new_cid != existing_cid:
                        id_remap[new_cid] = existing_cid
                    chars_to_remove.append(nc_name)
            if id_remap:
                from app.core import store
                async with store.atomic_update() as data:
                    for p in data["projects"]:
                        if p["id"] == self.project_id:
                            for ep_in in p["episodes"]:
                                if ep_in["id"] == self.episode_id:
                                    for d in ep_in["dialogues"]:
                                        if d.get("character_id") in id_remap:
                                            d["character_id"] = id_remap[d["character_id"]]
                                    break
                            # 移除重复角色
                            p["characters"] = [c for c in p["characters"] if c["name"] not in chars_to_remove]
                            break
                proj["characters"] = [c for c in proj["characters"] if c["name"] not in chars_to_remove]
                new_chars = [n for n in new_chars if n not in chars_to_remove]

        if new_chars:
            yield "new_characters", {"names": new_chars}

        yield "complete", {
            "created": len(created),
            "dialogue_ids": created,
            "new_characters": new_chars,
            "_debug": {
                "target": target_total,
                "scenes": len(scenes_plan),
                "actual": len(dialogues_data),
            },
        }


async def run_dialogue_generation(project_id: str, episode_id: str, body, task_id: str):
    """后台任务包装函数：消费 DialogueGenerator 的 async generator，
    将 yield 事件映射为 store.update_generation_task() 调用。

    这样 DialogueGenerator 本身零改动，所有 yield 事件被消费并持久化到 store。
    """
    from app.core.store import update_generation_task

    gen = DialogueGenerator(project_id, episode_id, body)
    throttle_counter = 0
    try:
        async for event_type, data in gen._generate_story():
            if event_type == "error":
                update_generation_task(project_id, task_id,
                    status="error", error=data.get("message", "未知错误"))
                return
            elif event_type == "progress":
                # 节流更新：每 5 条更新一次，避免高频 JSON 写入
                throttle_counter += 1
                if throttle_counter % 5 == 0:
                    update_generation_task(project_id, task_id,
                        current=data.get("current", 0), total=data.get("total", 0))
            elif event_type == "complete":
                # 完成事件：标记 complete，携带结果数据
                update_generation_task(project_id, task_id,
                    status="complete", current=data.get("created", 0),
                    total=data.get("created", 0), result=data)
                return
            elif event_type in ("generating", "story_parsed", "scene_start", "planning", "new_characters"):
                # 中间状态事件：更新状态描述
                update_generation_task(project_id, task_id,
                    status=f"running:{event_type}", extra=data)
    except Exception as e:
        import traceback
        update_generation_task(project_id, task_id,
            status="error", error=f"后台任务异常: {e}\n{traceback.format_exc()}")


async def run_batch_refresh(project_id: str, episode_id: str, dialogue_ids: list[str], task_id: str):
    """后台批量刷新对白状态（原 SSE 流式逻辑，改为通过 update_generation_task 更新进度）。"""
    from app.core.store import update_generation_task
    from app.api.episodes import get_episode, _refresh_single_dialogue
    from app.core.task_manager import TaskManager
    try:
        ep = get_episode(project_id, episode_id)
        if not ep:
            update_generation_task(project_id, task_id, status="error", error="Episode not found")
            return
        ok = 0
        fail = 0
        for i, dlg_id in enumerate(dialogue_ids):
            try:
                _dlg = None
                for d in ep["dialogues"]:
                    if d["id"] == dlg_id:
                        _dlg = d
                        break
                if not _dlg:
                    fail += 1
                    update_generation_task(project_id, task_id, current=i + 1)
                    continue
                await _refresh_single_dialogue(project_id, episode_id, _dlg)
                ok += 1
                update_generation_task(project_id, task_id, current=i + 1)
            except Exception as e:
                fail += 1
                update_generation_task(project_id, task_id, current=i + 1)
        update_generation_task(project_id, task_id, status="complete", current=ok + fail)
    except Exception as e:
        update_generation_task(project_id, task_id, status="error", error=str(e))
    finally:
        TaskManager.release(episode_id, "refresh")


async def run_batch_generate(project_id: str, episode_id: str, dialogue_ids: list[str], task_id: str):
    """后台批量提交 TTS 任务（原 SSE 流式逻辑，改为通过 update_generation_task 更新进度）。"""
    from app.core.store import update_generation_task
    from app.api.episodes import get_episode, get_project, _resolve_dialogue_tts_params, _download_and_save
    from app.api.episodes import submit_tts
    from app.core.task_manager import TaskManager
    import uuid
    import asyncio
    try:
        ep = get_episode(project_id, episode_id)
        proj = get_project(project_id)
        if not ep or not proj:
            update_generation_task(project_id, task_id, status="error", error="Episode or project not found")
            return
        submitted = 0
        failed_list = []
        for i, dlg_id in enumerate(dialogue_ids):
            dlg = None
            for d in ep["dialogues"]:
                if d["id"] == dlg_id:
                    dlg = d
                    break
            if not dlg:
                failed_list.append(dlg_id)
                update_generation_task(project_id, task_id, current=i + 1)
                continue
            try:
                tts_kwargs = _resolve_dialogue_tts_params(project_id, dlg, proj)
                task_id_inner = await submit_tts(**tts_kwargs)
                submitted += 1
                placeholder_id = f"gen_{uuid.uuid4().hex[:8]}"
                from app.core import store
                async with store.atomic_update() as data:
                    for p in data["projects"]:
                        if p["id"] == project_id:
                            for ep_in in p["episodes"]:
                                if ep_in["id"] == episode_id:
                                    for d in ep_in["dialogues"]:
                                        if d["id"] == dlg_id:
                                            from datetime import datetime
                                            d["audio_history"].append({
                                                "id": placeholder_id,
                                                "url": "",
                                                "filename": "",
                                                "created_at": datetime.now().isoformat(),
                                                "status": "generating",
                                                "task_id": task_id_inner,
                                            })
                                            d["current_audio_id"] = placeholder_id
                                            d["status"] = "generating"
                                    break
                            break
                asyncio.create_task(_download_and_save(project_id, episode_id, dlg_id, task_id_inner, placeholder_id))
                update_generation_task(project_id, task_id, current=submitted + len(failed_list))
            except Exception as e:
                failed_list.append(dlg_id)
                update_generation_task(project_id, task_id, current=submitted + len(failed_list))
        update_generation_task(project_id, task_id, status="complete", current=submitted + len(failed_list))
    except Exception as e:
        update_generation_task(project_id, task_id, status="error", error=str(e))
    finally:
        TaskManager.release(episode_id, "generate_batch")
