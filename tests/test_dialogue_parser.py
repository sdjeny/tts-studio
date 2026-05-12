"""单元测试：对白解析器 _parse_story_text 和角色匹配 _resolve_char_id (Refs #19)

覆盖范围:
- T9: _parse_story_text — 基本格式、无情绪标注、空文本过滤、多行合并、markdown 清理、order 递增
- T10: _resolve_char_id — 精确匹配、归一化匹配、模糊匹配、新角色创建
"""

import pytest
import re
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 辅助：构造最小 DialogueGenerator 实例，绕过 __init__ 中的 store 依赖
# ---------------------------------------------------------------------------

def _make_generator(characters=None):
    """创建一个最小化的 DialogueGenerator 实例，mock 掉 store 依赖。"""
    with patch("app.core.dialogue_service.get_project") as mock_gp, \
         patch("app.core.dialogue_service.get_episode") as mock_ge:
        mock_gp.return_value = {
            "id": "proj-1",
            "characters": characters or [],
            "episodes": [],
        }
        mock_ge.return_value = {"id": "ep-1", "title": "测试集", "summary": "测试摘要"}

        from app.core.dialogue_service import DialogueGenerator
        gen = DialogueGenerator("proj-1", "ep-1", MagicMock())
    return gen


# ===================================================================
# T9: _parse_story_text 测试
# ===================================================================

class TestParseStoryText:
    """测试 DialogueGenerator._parse_story_text"""

    def setup_method(self):
        self.gen = _make_generator()

    def test_basic_format(self):
        """基本格式：[角色名]（情绪）内容"""
        text = "[旁白] 夜色沉沉，雨后的街灯。\n[小明]（沉声）这纸张已经发黄。\n[小红]（活泼）哎呀，明哥。"
        result = self.gen._parse_story_text(text)

        assert len(result) == 3
        assert result[0]["role"] == "旁白"
        assert result[0]["instruct"] == ""
        assert result[0]["text"] == "夜色沉沉，雨后的街灯。"
        assert result[1]["role"] == "小明"
        assert result[1]["instruct"] == "沉声"
        assert result[1]["text"] == "这纸张已经发黄。"
        assert result[2]["role"] == "小红"
        assert result[2]["instruct"] == "活泼"
        assert result[2]["text"] == "哎呀，明哥。"

    def test_no_instruct(self):
        """无情绪标注 — instruct 应为空字符串"""
        text = "[小明] 你觉得呢？"
        result = self.gen._parse_story_text(text)

        assert len(result) == 1
        assert result[0]["role"] == "小明"
        assert result[0]["instruct"] == ""
        assert result[0]["text"] == "你觉得呢？"

    def test_empty_text_filtered(self):
        """空文本段应被过滤 — 末尾只有角色标记但无内容"""
        # 注意：由于正则中 \s* 会吞掉换行符，只有当空文本在末尾时才能被过滤
        text = "[小明]（沉声）实际内容。\n[旁白] "
        result = self.gen._parse_story_text(text)

        # 旁白的 text 为空（只有空格），应被过滤
        assert len(result) == 1
        assert result[0]["role"] == "小明"
        assert result[0]["text"] == "实际内容。"

    def test_empty_text_filtered_at_eof(self):
        """单独的角色标记在字符串末尾，无内容应被过滤"""
        text = "[旁白]"
        result = self.gen._parse_story_text(text)
        assert result == []

    def test_multiline_text(self):
        """多行文本合并到同一段落"""
        text = "[旁白] 第一行。\n第二行。\n第三行。\n[小明]（低声）对话内容。"
        result = self.gen._parse_story_text(text)

        assert len(result) == 2
        assert result[0]["role"] == "旁白"
        # 多行内容应包含换行符合并
        assert "第一行。" in result[0]["text"]
        assert "第二行。" in result[0]["text"]
        assert "第三行。" in result[0]["text"]
        assert result[1]["role"] == "小明"
        assert result[1]["text"] == "对话内容。"

    def test_markdown_code_block_cleaned(self):
        """清理 markdown 代码块标记"""
        text = "[小明]（沉声）```json\n实际内容。\n```"
        result = self.gen._parse_story_text(text)

        assert len(result) == 1
        assert "```" not in result[0]["text"]
        assert "实际内容。" in result[0]["text"]

    def test_order_increment(self):
        """解析结果顺序与输入一致（入库顺序递增）"""
        text = "[A] 第一段。\n[B] 第二段。\n[C] 第三段。\n[D] 第四段。"
        result = self.gen._parse_story_text(text)

        assert len(result) == 4
        roles = [item["role"] for item in result]
        assert roles == ["A", "B", "C", "D"]

    def test_empty_input(self):
        """空文本返回空列表"""
        result = self.gen._parse_story_text("")
        assert result == []

    def test_role_with_spaces(self):
        """角色名中的空格应被 strip"""
        text = "[  旁白  ] 无风的夜晚。"
        result = self.gen._parse_story_text(text)

        assert len(result) == 1
        assert result[0]["role"] == "旁白"

    def test_instruct_with_special_chars(self):
        """情绪标注包含中文标点"""
        text = "[小明]（略带紧张，低沉）这不对劲。"
        result = self.gen._parse_story_text(text)

        assert len(result) == 1
        assert result[0]["instruct"] == "略带紧张，低沉"
        assert result[0]["text"] == "这不对劲。"


# ===================================================================
# T10: _resolve_char_id 测试
# ===================================================================

class TestResolveCharId:
    """测试 DialogueGenerator._resolve_char_id"""

    def test_exact_match(self):
        """精确匹配已有角色"""
        gen = _make_generator(characters=[
            {"id": "c1", "name": "小明", "voice_id": "aiden"},
            {"id": "c2", "name": "小红", "voice_id": "serena"},
        ])
        cache = {}
        char_id, is_new = gen._resolve_char_id("小明", cache)
        assert char_id == "c1"
        assert is_new is False

    def test_exact_match_second_char(self):
        """精确匹配第二个角色"""
        gen = _make_generator(characters=[
            {"id": "c1", "name": "小明", "voice_id": "aiden"},
            {"id": "c2", "name": "小红", "voice_id": "serena"},
        ])
        cache = {}
        char_id, is_new = gen._resolve_char_id("小红", cache)
        assert char_id == "c2"
        assert is_new is False

    def test_cache_hit(self):
        """本次已创建的角色从缓存中匹配"""
        gen = _make_generator(characters=[])
        cache = {"新角色": "c-new-1"}
        char_id, is_new = gen._resolve_char_id("新角色", cache)
        assert char_id == "c-new-1"
        assert is_new is False

    def test_normalize_match(self):
        """归一化匹配 — 角色名含特殊字符时归一化后匹配"""
        gen = _make_generator(characters=[
            {"id": "c1", "name": "小·明", "voice_id": "aiden"},
        ])
        cache = {}
        # "小明" 归一化后应匹配 "小·明"（去掉中间的 ·）
        char_id, is_new = gen._resolve_char_id("小明", cache)
        assert char_id == "c1"
        assert is_new is False

    def test_fuzzy_match(self):
        """模糊匹配 — SequenceMatcher 相似度 >= 0.7"""
        gen = _make_generator(characters=[
            {"id": "c1", "name": "欧阳明月", "voice_id": "aiden"},
        ])
        cache = {}
        # "欧阳明" 与 "欧阳明月" 相似度较高
        char_id, is_new = gen._resolve_char_id("欧阳明", cache)
        assert char_id == "c1"
        assert is_new is False

    def test_new_character_created(self):
        """无匹配时创建新角色"""
        gen = _make_generator(characters=[
            {"id": "c1", "name": "小明", "voice_id": "aiden"},
        ])
        cache = {}

        with patch("app.core.dialogue_service.add_character") as mock_add:
            mock_add.return_value = {"id": "c-new", "name": "陌生人", "voice_id": "aiden"}
            char_id, is_new = gen._resolve_char_id("陌生人", cache)

        assert char_id == "c-new"
        assert is_new is True
        assert cache["陌生人"] == "c-new"

    def test_no_characters_no_match(self):
        """空角色列表时，新角色也会被创建"""
        gen = _make_generator(characters=[])
        cache = {}

        with patch("app.core.dialogue_service.add_character") as mock_add:
            mock_add.return_value = {"id": "c-new", "name": "独白者", "voice_id": "aiden"}
            char_id, is_new = gen._resolve_char_id("独白者", cache)

        assert char_id == "c-new"
        assert is_new is True

    def test_substring_match(self):
        """互相包含匹配"""
        gen = _make_generator(characters=[
            {"id": "c1", "name": "欧阳明月", "voice_id": "aiden"},
        ])
        cache = {}
        # "明月" 是 "欧阳明月" 的子串，应命中包含匹配
        char_id, is_new = gen._resolve_char_id("明月", cache)
        assert char_id == "c1"
        assert is_new is False

    def test_add_character_failure(self):
        """add_character 返回 None 时不创建新角色"""
        gen = _make_generator(characters=[])
        cache = {}

        with patch("app.core.dialogue_service.add_character") as mock_add:
            mock_add.return_value = None
            char_id, is_new = gen._resolve_char_id("幽灵", cache)

        assert char_id == ""
        assert is_new is False
        assert "幽灵" not in cache

    def test_voice_id_from_existing(self):
        """新建角色的 voice_id 继承自已有角色"""
        gen = _make_generator(characters=[
            {"id": "c1", "name": "小明", "voice_id": "serena"},
        ])
        cache = {}

        with patch("app.core.dialogue_service.add_character") as mock_add:
            mock_add.return_value = {"id": "c-new", "name": "新人", "voice_id": "serena"}
            gen._resolve_char_id("新人", cache)

            # 验证 voice_id 传入正确
            call_args = mock_add.call_args
            assert call_args[0][2] == "serena"  # voice_id 参数
