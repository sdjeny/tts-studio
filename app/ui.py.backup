import gradio as gr
import asyncio
import os
import time
import uuid
from pydub import AudioSegment
from .models import current_project, ScriptLine, AudioClip
from .config import DEFAULT_API_BASE, DEFAULT_API_KEY, DEFAULT_MODEL, DEFAULT_VOICES, VOICE_OPTIONS, PROJECTS_DIR
from .llm_parser import parse_with_llm
from .tts_engine import synthesize_single_line, mix_audio_tracks
from .project_manager import script_lines_to_clips, load_project_from_file, save_project_to_file

def build_ui():
    # 🔑 全局变量：跟踪当前工程的文件路径
    current_project_path = None
    
    # 手动初始化工程列表（避免使用 demo.load 导致性能问题）
    import logging
    logger = logging.getLogger(__name__)
    logger.info("🚀 应用启动，手动初始化工程列表...")
    
    # 🔑 封装：创建确认对话框组件（可复用）
    def create_confirm_dialog(warning_text: str, confirm_text: str = "✅ 确认", cancel_text: str = "❌ 取消"):
        """
        创建带红色边框的确认对话框组件（按钮在框内）
        
        Args:
            warning_text: 警告信息
            confirm_text: 确认按钮文字
            cancel_text: 取消按钮文字
            
        Returns:
            tuple: (confirm_row, warning_md, confirm_btn, cancel_btn)
        """
        # 确认对话框（红色边框容器）
        with gr.Row(visible=False) as confirm_row:
            with gr.Column(elem_classes="confirm-box"):
                # 警告文本
                warning_md = gr.Markdown(
                    f"<div class='confirm-text'>{warning_text}</div>"
                )
                # 按钮区域（在框内）
                with gr.Row():
                    confirm_btn = gr.Button(confirm_text, variant="stop", size="sm")
                    cancel_btn = gr.Button(cancel_text, size="sm")
        
        return confirm_row, warning_md, confirm_btn, cancel_btn
    
    # 🔑 封装：显示确认对话框
    def show_confirm_dialog(confirm_row, warning_md, message: str):
        """显示确认对话框并更新警告信息"""
        return (
            gr.update(visible=True),
            gr.update(value=f"<div style='padding:10px 10px 5px 10px;color:#cf1322;font-weight:bold;'>{message}</div>")
        )
    
    # 🔑 封装：隐藏确认对话框
    def hide_confirm_dialog(confirm_row, warning_md):
        """隐藏确认对话框并清空警告信息"""
        return (
            gr.update(visible=False),
            gr.update(value="")
        )
    
    from pathlib import Path
    projects_dir = Path(PROJECTS_DIR)
    if projects_dir.exists():
        # 使用文件名而不是完整路径
        files = sorted([f.name for f in projects_dir.glob("*.json")], key=lambda x: (projects_dir / x).stat().st_mtime, reverse=True)
        logger.info(f"找到 {len(files)} 个工程文件")
    else:
        files = []
        logger.warning(f"工程目录不存在: {PROJECTS_DIR}")
    
    initial_choices = files if files else []
    initial_value = files[0] if files else None
    
    # 如果有初始工程，预加载数据
    initial_clips_data = []
    initial_project_name = "未命名"
    initial_input_text = ""
    initial_api_base = DEFAULT_API_BASE
    initial_api_key = DEFAULT_API_KEY
    initial_model = DEFAULT_MODEL
    initial_projects_data = []  # 🔑 工程管理表格初始数据
    
    if initial_value:
        logger.info(f"默认选中: {initial_value}")
        try:
            file_path = PROJECTS_DIR / initial_value
            if file_path.exists():
                loaded_project = load_project_from_file(str(file_path))
                # 更新全局 current_project
                current_project.name = loaded_project.name
                current_project.raw_text = loaded_project.raw_text
                current_project.script_lines = loaded_project.script_lines
                current_project.audio_clips = loaded_project.audio_clips
                current_project.llm_config = loaded_project.llm_config
                current_project.character_voices = loaded_project.character_voices
                current_project.bgm_clips = getattr(loaded_project, 'bgm_clips', [])
                current_project.sfx_clips = getattr(loaded_project, 'sfx_clips', [])
                current_project.characters = getattr(loaded_project, 'characters', [])  # 🔑 加载角色数据
                
                # 🔑 记录当前工程路径
                current_project_path = str(file_path)
                logger.info(f"  当前工程路径: {current_project_path}")
                
                # 准备初始数据
                def refresh_clips_table():
                    if not current_project.audio_clips:
                        return []
                    data = []
                    for c in current_project.audio_clips:
                        text_preview = c.text[:50] + "..." if len(c.text) > 50 else c.text
                        status_icon = "✅" if c.is_generated else "⏳"
                        # 3列结构：选中标记、角色+状态、文本
                        data.append([
                            "",                                  # 第1列：选中标记（初始为空）
                            f"{c.character} {status_icon}",      # 第2列：角色+状态
                            text_preview                         # 第3列：文本
                        ])
                    return data
                
                initial_clips_data = refresh_clips_table()
                initial_project_name = current_project.name
                initial_input_text = current_project.raw_text
                initial_api_base = current_project.llm_config.get("api_base", DEFAULT_API_BASE)
                initial_api_key = current_project.llm_config.get("api_key", DEFAULT_API_KEY)
                initial_model = current_project.llm_config.get("model", DEFAULT_MODEL)
                
                # 🔑 初始化工程管理表格数据
                def get_projects_list_init():
                    """获取工程列表（初始化用）"""
                    if not PROJECTS_DIR.exists():
                        return []
                    json_files = list(PROJECTS_DIR.glob("*.json"))
                    if not json_files:
                        return []
                    json_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    data = []
                    for i, f in enumerate(json_files):
                        stat = f.stat()
                        import datetime
                        mod_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                        size_kb = stat.st_size / 1024
                        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
                        selected_mark = "▶" if i == 0 else ""
                        data.append([selected_mark, f.name, mod_time, size_str])
                    return data
                
                initial_projects_data = get_projects_list_init()
                
                # 🔑 初始化角色相关数据
                def refresh_characters_table_init():
                    """刷新角色列表表格（初始化用）"""
                    if not current_project.characters:
                        return []
                    data = []
                    for c in current_project.characters:
                        data.append([
                            "",  # 选中标记（初始为空）
                            c.name,
                            c.voice_id,
                            c.rate,
                            c.pitch,
                            c.personality[:20] if c.personality else ""
                        ])
                    return data
                
                def get_character_choices_init():
                    """获取角色选择列表（初始化用）"""
                    if not current_project.characters:
                        return []
                    return [c.name for c in current_project.characters]
                
                initial_characters_data = refresh_characters_table_init()
                initial_character_choices = get_character_choices_init()
                
                logger.info(f"✅ 预加载成功: {current_project.name}")
                logger.info(f"  音频片段数: {len(current_project.audio_clips)}")
                logger.info(f"  角色数: {len(current_project.characters)}")
        except Exception as e:
            logger.error(f"❌ 预加载失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    # 自定义CSS防止确认框被Gradio加载状态覆盖
    custom_css = """
    .confirm-box {
        border: 2px solid #ff4d4f !important;
        border-radius: 8px !important;
        background: #fff2f0 !important;
        padding: 12px !important;
    }
    .confirm-box * {
        border-color: #ff4d4f !important;
    }
    .confirm-text {
        color: #cf1322 !important;
        font-weight: bold !important;
        font-size: 14px !important;
        margin-bottom: 10px !important;
    }
    /* 防止Gradio加载状态改变边框颜色 */
    .confirm-box.generating {
        border-color: #ff4d4f !important;
        background: #fff2f0 !important;
    }
    """
    
    with gr.Blocks(title="多轨剧本配音工作台") as demo:
        gr.Markdown("# 🎛️ 多轨剧本配音工作台")
        
        with gr.Tabs():
            # Tab 1: 工程与配置
            with gr.TabItem("📁 工程与配置"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 📝 工程信息")
                        project_name = gr.Textbox(label="工程名", value=initial_project_name)
                        
                        with gr.Row():
                            new_project_btn = gr.Button("✨ 新建工程", size="sm")
                            save_project_btn = gr.Button("💾 保存工程", variant="primary", size="sm")
                            load_project_btn = gr.UploadButton("📂 加载工程", file_types=[".json"], size="sm")
                        
                        # 🔑 工程保存覆盖确认区域（使用封装组件）
                        save_confirm_row, save_warning_text, confirm_save_btn, cancel_save_btn = create_confirm_dialog(
                            warning_text="⚠️ 工程已存在，是否覆盖保存？",
                            confirm_text="✅ 覆盖保存",
                            cancel_text="❌ 取消"
                        )
                        
                        project_status = gr.Textbox(label="保存状态", interactive=False, visible=True)
                    
                    with gr.Column(scale=1):
                        gr.Markdown("### 📋 工程管理")
                        projects_table = gr.Dataframe(
                            headers=["选中", "工程名称", "修改时间", "文件大小"],
                            datatype=["str", "str", "str", "str"],
                            label="",  # 🔑 去掉label
                            interactive=False,
                            row_count=2,
                            wrap=True,
                            column_count=4,
                            value=initial_projects_data,
                            elem_classes="compact-table"
                        )
                        # 🔑 隐藏变量：记录选中的工程行索引
                        selected_project_index = gr.Number(value=-1, visible=False)
                        
                        with gr.Row():
                            load_selected_btn = gr.Button("📂 加载选中工程", variant="primary", size="sm")
                            delete_selected_btn = gr.Button("🗑️ 删除选中工程", size="sm", variant="stop")
                            refresh_projects_btn = gr.Button("🔄 刷新列表", size="sm")
                        
                        # 🔑 删除确认区域（使用封装组件）
                        delete_confirm_row, delete_warning_text, confirm_delete_btn, cancel_delete_btn = create_confirm_dialog(
                            warning_text="⚠️ 确定要删除该工程吗？此操作不可恢复！",
                            confirm_text="✅ 确认删除",
                            cancel_text="❌ 取消"
                        )
                
                # LLM配置在下面占一整行
                gr.Markdown("### ⚙️ LLM 配置")
                with gr.Row():
                    api_base = gr.Textbox(label="API Base", value=initial_api_base, scale=2)
                    api_key = gr.Textbox(label="API Key", value=initial_api_key, type="password", scale=2)
                    model = gr.Textbox(label="模型", value=initial_model, scale=1)
                gr.Markdown("*LLM 用于自动解析剧本文本，识别角色和对白*")
                
                # 🔑 角色管理面板
                with gr.Accordion("🎭 角色管理", open=False):
                    gr.Markdown("#### 📋 角色列表")
                    characters_table = gr.Dataframe(
                        headers=["选中", "角色名", "音色", "语速", "音调", "性格摘要"],
                        datatype=["str", "str", "str", "str", "str", "str"],
                        label="已定义的角色",
                        interactive=True,
                        row_count=(5, "dynamic"),
                        wrap=True,
                        column_count=(6, "fixed"),
                        value=initial_characters_data  # 🔑 设置初始值
                    )
                    
                    # 🔑 隐藏变量：记录选中的角色行索引
                    selected_char_index = gr.Number(value=-1, visible=False)
                    
                    with gr.Row():
                        refresh_chars_btn = gr.Button("🔄 刷新列表", size="sm")
                        add_char_btn = gr.Button("➕ 新建角色", variant="primary", size="sm")
                        delete_char_btn = gr.Button("🗑️ 删除角色", size="sm")
                    
                    gr.Markdown("#### ✏️ 编辑角色")
                    with gr.Row():
                        with gr.Column(scale=1):
                            char_name_input = gr.Textbox(label="角色名称", placeholder="如：李远、旁白")
                            char_voice_input = gr.Dropdown(
                                label="音色",
                                choices=VOICE_OPTIONS,
                                value="zh-CN-YunjianNeural",
                                interactive=True
                            )
                            char_rate_input = gr.Slider(-50, 50, 0, step=5, label="语速 (%)")
                            char_pitch_input = gr.Slider(-20, 20, 0, step=5, label="音调 (Hz)")
                            char_volume_input = gr.Slider(0.0, 2.0, 1.0, step=0.1, label="音量")
                        
                        with gr.Column(scale=2):
                            char_personality_input = gr.Textbox(
                                label="性格摘要",
                                placeholder="如：沉稳、内敛、理性",
                                lines=2
                            )
                            char_description_input = gr.Textbox(
                                label="角色介绍",
                                placeholder="详细描述角色的背景、特点等",
                                lines=3
                            )
                            char_age_input = gr.Textbox(label="年龄段", placeholder="如：青年、中年")
                            char_gender_input = gr.Radio(
                                choices=[("男", "male"), ("女", "female"), ("其他", "other")],
                                label="性别",
                                value="male"
                            )
                            char_emotion_style_input = gr.Textbox(
                                label="情绪风格",
                                placeholder="如：冷静、激昂、温柔",
                                lines=2
                            )
                            char_notes_input = gr.Textbox(
                                label="备注",
                                placeholder="其他说明",
                                lines=2
                            )
                    
                    with gr.Row():
                        save_char_btn = gr.Button("💾 保存角色", variant="primary")
                        clear_char_form_btn = gr.Button("🧹 清空表单", size="sm")
                    
                    # 🔑 角色覆盖确认区域（使用封装组件）
                    char_confirm_row, char_warning_text, confirm_char_btn, cancel_char_btn = create_confirm_dialog(
                        warning_text="⚠️ 角色已存在，是否覆盖保存？",
                        confirm_text="✅ 确认覆盖",
                        cancel_text="❌ 取消"
                    )
                    
                    char_status = gr.Textbox(label="状态", interactive=False)
            
            # Tab 2: 文本解析
            with gr.TabItem("📝 文本解析"):
                gr.Markdown("### 📖 输入剧本文本")
                input_text = gr.Textbox(
                    label="粘贴小说或剧本",
                    placeholder="支持任意格式，LLM 会自动解析角色和对白",
                    lines=8,
                    value=initial_input_text
                )
                with gr.Row():
                    parse_btn = gr.Button("🔍 LLM 解析", variant="primary", size="lg")
                    clear_btn = gr.Button("🧹 清空", size="lg")
            
            # Tab 3: 对白编辑
            with gr.TabItem("🎤 对白编辑"):
                with gr.Row():
                    # 左侧：表格 + SSML 文本框
                    with gr.Column(scale=3):
                        gr.Markdown("### 🎭 对白片段列表")
                        clips_table = gr.Dataframe(
                            headers=["选中", "角色", "文本"],
                            datatype=["str", "str", "str"],
                            label="对白片段（点击选中后可编辑）",
                            interactive=True,
                            row_count=(10, "dynamic"),
                            wrap=True,
                            column_count=(3, "fixed"),
                            value=initial_clips_data
                        )
                        
                        with gr.Row():
                            selected_row_index = gr.Number(value=-1, visible=False)
                            apply_edit_btn = gr.Button("✅ 应用修改", variant="primary")
                            generate_selected_btn = gr.Button("🎙️ 生成选中", size="sm")
                            preview_selected_btn = gr.Button("🔊 预听", size="sm")
                            generate_all_btn = gr.Button("🎬 生成全部", variant="primary", size="lg")
                        
                        # SSML 标记文本（直接发送给 TTS）
                        ssml_text_display = gr.Textbox(
                            label="SSML 标记文本（直接发送给 TTS）",
                            placeholder="编辑多音字、停顿、语气等标记",
                            lines=6,
                            interactive=True
                        )
                        # 🔑 关键：应用属性按钮放在 SSML 文本框下方
                        apply_clip_props_btn = gr.Button("✅ 应用属性（SSML + 音色参数）", variant="primary")
                    
                    # 右侧：细长的属性控件
                    with gr.Column(scale=2):
                        gr.Markdown("#### 📝 当前选中对白的详细属性")
                        
                        gr.Markdown("#### 🎭 角色选择")
                        with gr.Row():
                            clip_character = gr.Dropdown(
                                label="从角色列表选择",
                                choices=initial_character_choices,  # 🔑 设置初始choices
                                value=None,
                                interactive=True,
                                allow_custom_value=False,
                                scale=3
                            )
                            manage_chars_btn = gr.Button("🎭 管理", size="sm", scale=1)
                        
                        # 🔑 角色管理提示信息
                        char_manage_hint = gr.Markdown("", visible=False)
                        
                        gr.Markdown("#### 🎚️ 音色与参数")
                        clip_voice = gr.Dropdown(
                            label="音色（可手动覆盖）",
                            choices=VOICE_OPTIONS,  # 使用 (显示名称, 真实ID) 元组
                            value="zh-CN-YunjianNeural",  # 默认值：真实的音色 ID
                            interactive=True,
                            allow_custom_value=False  # 不允许自定义，只能从列表选择
                        )
                        clip_rate = gr.Slider(-50, 50, 0, step=5, label="语速 (%)")
                        clip_pitch = gr.Slider(-20, 20, 0, step=5, label="音调 (Hz)")
                        clip_volume = gr.Slider(0.0, 2.0, 1.0, step=0.1, label="音量")
                        
                        gr.Markdown("#### 🔤 多音字标注")
                        with gr.Row():
                            phoneme_char_input = gr.Textbox(
                                label="待标注字",
                                placeholder="例：行",
                                scale=1
                            )
                            phoneme_replace_input = gr.Textbox(
                                label="替换为",
                                placeholder="例：航",
                                scale=1
                            )
                        add_phoneme_btn = gr.Button("➕ 标注", size="sm")
                        
                        gr.Markdown("#### ⏸️ 插入停顿")
                        with gr.Row():
                            pause_duration = gr.Slider(
                                100, 2000, 300, step=50,
                                label="时长(ms)",
                                scale=2
                            )
                            add_pause_btn = gr.Button("⏸️ 插入", size="sm", scale=1)
                        
                        gr.Markdown("#### ❗ 添加强调")
                        with gr.Row():
                            emphasis_preset = gr.Dropdown(
                                choices=[
                                    ("强烈", "strong"),
                                    ("中等", "moderate"),
                                    ("减弱", "reduced"),
                                    ("极慢强调", "very_slow"),
                                    ("快速激昂", "fast_excited"),
                                    ("低音沉稳", "low_pitch"),
                                    ("高音尖锐", "high_pitch"),
                                    ("慢速+停顿", "slow_pause"),
                                    ("自定义", "custom")
                                ],
                                value="strong",
                                label="预设",
                                scale=2
                            )
                            add_emphasis_btn = gr.Button("❗ 添加", size="sm", scale=1)
                        
                        with gr.Row():
                            emphasis_target = gr.Textbox(
                                label="目标文本（可选）",
                                placeholder="留空则对整个文本生效",
                                scale=2
                            )
                        
                        with gr.Row():
                            emphasis_rate = gr.Textbox(value="-20", label="语速 rate (%)", scale=1)
                            emphasis_pitch = gr.Textbox(value="-20", label="音调 pitch (Hz)", scale=1)
                            emphasis_volume = gr.Textbox(value="10", label="音量 volume (%)", scale=1)
                        
                        with gr.Row():
                            clear_markers_btn = gr.Button("🧹 清除标记", size="sm")
                            preview_marked_btn = gr.Button("🔊 试听", size="sm")
                        
                        marked_audio_preview = gr.Audio(label="预听", type="filepath", visible=False)
                        editor_status = gr.Textbox(label="状态", interactive=False)
        
            # Tab 4: 混音输出
            with gr.TabItem("🎧 混音输出"):
                gr.Markdown("### 🎵 背景乐/音效")
                with gr.Accordion("添加音轨", open=True):
                    bgm_file = gr.Audio(label="上传背景乐", type="filepath")
                    bgm_volume = gr.Slider(0.0, 2.0, 0.3, label="背景乐音量")
                    add_bgm_btn = gr.Button("➕ 添加背景乐")
                    
                    sfx_name = gr.Textbox(label="音效名称", placeholder="敲门声")
                    sfx_file = gr.Audio(label="上传音效", type="filepath")
                    sfx_start = gr.Number(0.0, label="开始时间(秒)")
                    sfx_volume = gr.Slider(0.0, 2.0, 1.0, label="音量")
                    add_sfx_btn = gr.Button("➕ 添加音效")
                
                gr.Markdown("### 🎼 最终混音")
                with gr.Row():
                    total_duration = gr.Number(0.0, label="总时长(秒), 0=自动")
                    mix_btn = gr.Button("🎧 合成混音", variant="primary", size="lg")
                final_audio = gr.Audio(label="成品混音", type="filepath")
        
        # 事件处理函数
        def update_llm_config(base, key, mdl):
            """更新LLM配置到当前工程"""
            current_project.llm_config = {"api_base": base, "api_key": key, "model": mdl}
        
        api_base.change(update_llm_config, [api_base, api_key, model], None)
        api_key.change(update_llm_config, [api_base, api_key, model], None)
        model.change(update_llm_config, [api_base, api_key, model], None)
        
        def update_project_name(name):
            current_project.name = name
        project_name.change(update_project_name, project_name, None)
        
        def refresh_clips_table(selected_idx=-1):
            """刷新对白表格，支持高亮选中行（3列结构）"""
            if not current_project.audio_clips:
                return []
            data = []
            for i, c in enumerate(current_project.audio_clips):
                text_preview = c.text[:50] + "..." if len(c.text) > 50 else c.text
                status_icon = "✅" if c.is_generated else "⏳"
                # 高亮选中行：在独立的第一列显示 ▶
                selected_mark = "▶" if i == selected_idx else ""
                data.append([
                    selected_mark,                      # 第1列：选中标记
                    f"{c.character} {status_icon}",      # 第2列：角色+状态
                    text_preview                         # 第3列：文本
                ])
            return data
        
        def parse_text(text, base, key, mdl):
            import logging
            logger = logging.getLogger(__name__)
            
            logger.info(f"=" * 60)
            logger.info(f"开始 LLM 解析")
            logger.info(f"  文本长度: {len(text)}")
            
            current_project.llm_config = {"api_base": base, "api_key": key, "model": mdl}
            current_project.raw_text = text
            parsed = parse_with_llm(text, base, key, mdl)
            
            logger.info(f"✅ LLM 解析完成，共 {len(parsed)} 条对白")
            
            lines = []
            characters_found = set()  # 🔑 收集所有角色名
            
            for item in parsed:
                char = item.get("character", "")
                if item["type"] == "narration":
                    char = "旁白"
                
                # 🔑 收集角色名
                if char and char not in characters_found:
                    characters_found.add(char)
                    logger.info(f"  发现角色: {char}")
                
                voice_cfg = current_project.character_voices.get(
                    char, 
                    DEFAULT_VOICES.get("旁白" if char == "旁白" else "默认男")
                )
                lines.append(ScriptLine(
                    type=item["type"],
                    character=char,
                    emotion=item.get("emotion", ""),
                    text=item["text"],
                    voice=voice_cfg["voice"],
                    rate=voice_cfg["rate"],
                    pitch=voice_cfg["pitch"]
                ))
            
            current_project.script_lines = lines
            current_project.audio_clips = script_lines_to_clips(lines)
            
            # 🔑 自动创建角色（如果不存在）
            created_chars = []
            for char_name in characters_found:
                existing = next((c for c in current_project.characters if c.name == char_name), None)
                if not existing:
                    # 创建新角色，使用默认配置
                    from .models import Character
                    voice_cfg = current_project.character_voices.get(
                        char_name,
                        DEFAULT_VOICES.get("旁白" if char_name == "旁白" else "默认男")
                    )
                    new_char = Character(
                        name=char_name,
                        voice_id=voice_cfg["voice"],
                        rate=voice_cfg["rate"],
                        pitch=voice_cfg["pitch"],
                        volume=1.0,
                        personality="",
                        description=f"从文本中自动识别的角色：{char_name}",
                        age="",
                        gender="",
                        emotion_style="",
                        notes=""
                    )
                    current_project.characters.append(new_char)
                    created_chars.append(char_name)
                    logger.info(f"  ✅ 自动创建角色: {char_name}")
            
            # 重置选中行
            clips_data = refresh_clips_table(-1)
            
            # 🔑 刷新角色相关数据
            characters_data = refresh_characters_table()
            character_choices = get_character_choices()
            
            status_msg = f"✅ 解析完成！共 {len(lines)} 条对白，{len(created_chars)} 个新角色"
            if created_chars:
                status_msg += f"\n🎭 已自动创建角色：{', '.join(created_chars)}"
            status_msg += "\n💡 请切换到【🎤 对白编辑】页签查看进度和生成音频"
            
            logger.info(status_msg)
            logger.info(f"{'=' * 60}")
            
            # 🔑 关键：使用 gr.update() 来同时更新 choices 和清空 value
            character_dropdown_update = gr.update(
                choices=character_choices,
                value=None  # 清空选择，避免 value 不在 choices 中的错误
            )
            
            return clips_data, status_msg, characters_data, character_dropdown_update
        
        parse_btn.click(parse_text, [input_text, api_base, api_key, model], [clips_table, editor_status, characters_table, clip_character])
        
        # 监听表格选择事件，记录选中的行号
        def on_table_select(evt: gr.SelectData):
            if evt.index:
                return evt.index[0]
            return -1
        
        def on_row_index_change(row_idx):
            """当选中行变化时，刷新表格显示高亮"""
            return refresh_clips_table(int(row_idx))
        
        clips_table.select(on_table_select, None, selected_row_index)
        selected_row_index.change(on_row_index_change, [selected_row_index], clips_table)
        
        async def generate_selected(row_index):
            """生成选中的片段"""
            row_idx = int(row_index)
            if row_idx < 0 or row_idx >= len(current_project.audio_clips):
                raise gr.Error("请先在表格中选中一行")
            clip = current_project.audio_clips[row_idx]
            line = next((l for l in current_project.script_lines 
                       if l.text == clip.text and l.character == clip.character), None)
            if line:
                duration = await synthesize_single_line(line, clip.file_path)
                clip.duration = duration
                clip.is_generated = True
                for i in range(row_idx + 1, len(current_project.audio_clips)):
                    current_project.audio_clips[i].start_time = (
                        current_project.audio_clips[i-1].start_time + current_project.audio_clips[i-1].duration
                    )
            return refresh_clips_table(row_idx)
        
        generate_selected_btn.click(generate_selected, [selected_row_index], clips_table)
        
        async def generate_all():
            for clip in current_project.audio_clips:
                if not clip.is_generated:
                    line = next((l for l in current_project.script_lines 
                               if l.text == clip.text and l.character == clip.character), None)
                    if line:
                        duration = await synthesize_single_line(line, clip.file_path)
                        clip.duration = duration
                        clip.is_generated = True
            # 保持当前选中行的高亮
            return refresh_clips_table(int(selected_row_index.value) if hasattr(selected_row_index, 'value') else -1)
        
        generate_all_btn.click(generate_all, None, clips_table)
        
        def apply_edit_to_clips(table_data):
            """应用对白表格的修改到 audio_clips"""
            import logging
            logger = logging.getLogger(__name__)
            
            try:
                logger.info(f"=" * 60)
                logger.info(f"应用表格修改")
                logger.info(f"  数据类型: {type(table_data)}")
                
                # Gradio Dataframe 返回的是 DataFrame 对象
                import pandas as pd
                if isinstance(table_data, pd.DataFrame):
                    if table_data.empty:
                        msg = "⚠️ 没有数据可应用"
                        logger.warning(msg)
                        return msg
                    table_data = table_data.values.tolist()
                    logger.info(f"  DataFrame 转换为列表，行数: {len(table_data)}")
                
                if not table_data or len(table_data) == 0:
                    msg = "⚠️ 没有数据可应用"
                    logger.warning(msg)
                    return msg
                
                logger.info(f"  总行数: {len(table_data)}")
                
                # 更新 audio_clips
                updated_count = 0
                for i, row in enumerate(table_data):
                    if i < len(current_project.audio_clips):
                        clip = current_project.audio_clips[i]
                        # row[0] 是选中标记，row[1] 是角色（可能包含状态图标），row[2] 是文本
                        character_with_status = row[1] if len(row) > 1 else clip.character
                        text = row[2] if len(row) > 2 else clip.text
                        
                        # 移除状态图标，提取纯角色名
                        character = character_with_status.replace(" ✅", "").replace(" ⏳", "")
                        
                        # 只有当数据变化时才更新
                        if clip.character != character or clip.text != text:
                            old_char = clip.character
                            old_text = clip.text[:20]
                            clip.character = character
                            clip.text = text
                            updated_count += 1
                            logger.info(f"  更新行 {i}: '{old_char}' -> '{character}', 文本: '{old_text}...' -> '{text[:20]}...'")
                        
                        # 同步更新 script_line
                        line = next((l for l in current_project.script_lines 
                                    if l.text == clip.text and l.character == clip.character), None)
                        if line:
                            line.character = character
                            line.text = text
                
                msg = f"✅ 已应用 {updated_count}/{len(table_data)} 条修改"
                logger.info(f"{msg}")
                logger.info(f"{'=' * 60}")
                return msg
                
            except Exception as e:
                error_msg = f"❌ 应用失败: {str(e)}"
                logger.error(f"{error_msg}")
                import traceback
                logger.error(traceback.format_exc())
                return error_msg
        
        apply_edit_btn.click(
            apply_edit_to_clips,
            [clips_table],
            editor_status
        )
        
        def preview_selected(row_index):
            """预听选中的音频片段"""
            row_idx = int(row_index)
            if row_idx < 0 or row_idx >= len(current_project.audio_clips):
                raise gr.Error("请先在表格中选中一行")
            clip = current_project.audio_clips[row_idx]
            if clip.is_generated and os.path.exists(clip.file_path):
                return clip.file_path
            raise gr.Error("该片段尚未生成")
        
        preview_selected_btn.click(preview_selected, [selected_row_index], gr.Audio(label="预听", type="filepath"))
        
        def mix_all(duration_input):
            all_clips = current_project.audio_clips + current_project.bgm_clips + current_project.sfx_clips
            total = duration_input if duration_input > 0 else None
            output_path = mix_audio_tracks(all_clips, total)
            return output_path
        
        mix_btn.click(mix_all, [total_duration], [final_audio])
        
        def add_bgm(file_path, volume):
            if file_path:
                clip = AudioClip(
                    id=uuid.uuid4().hex[:8],
                    type="bgm",
                    character="BGM",
                    text="",
                    file_path=file_path,
                    voice="",
                    rate="",
                    pitch="",
                    volume=volume,
                    start_time=0.0,
                    duration=AudioSegment.from_file(file_path).duration_seconds,
                    is_generated=True
                )
                current_project.bgm_clips.append(clip)
            return "背景乐已添加"
        
        add_bgm_btn.click(add_bgm, [bgm_file, bgm_volume], None)
        
        def add_sfx(name, file_path, start, volume):
            if file_path:
                clip = AudioClip(
                    id=uuid.uuid4().hex[:8],
                    type="sfx",
                    character=name or "SFX",
                    text="",
                    file_path=file_path,
                    voice="",
                    rate="",
                    pitch="",
                    volume=volume,
                    start_time=start,
                    duration=AudioSegment.from_file(file_path).duration_seconds,
                    is_generated=True
                )
                current_project.sfx_clips.append(clip)
            return "音效已添加"
        
        add_sfx_btn.click(add_sfx, [sfx_name, sfx_file, sfx_start, sfx_volume], None)
        
        def prepare_save_project():
            """准备保存工程，检查是否需要覆盖确认"""
            import logging
            logger = logging.getLogger(__name__)
            nonlocal current_project_path
            
            # 检查是否已有工程路径（即是否为覆盖保存）
            if current_project_path and os.path.exists(current_project_path):
                # 覆盖保存，需要确认
                file_name = os.path.basename(current_project_path)
                logger.info(f"💾 请求覆盖保存工程: {file_name}（等待确认）")
                warning_msg = f"⚠️ 工程已存在，是否覆盖保存？<br><br>📁 <b>{file_name}</b><br>⚠️ 现有工程文件将被替换！"
                return show_confirm_dialog(save_confirm_row, save_warning_text, warning_msg)
            else:
                # 新工程，直接保存
                return execute_save_project()
        
        def execute_save_project():
            """执行保存工程操作"""
            import logging
            logger = logging.getLogger(__name__)
            nonlocal current_project_path
            
            # 确定保存路径
            if current_project_path and os.path.exists(current_project_path):
                # 覆盖保存
                path = current_project_path
                is_overwrite = True
                logger.info(f"🔄 覆盖保存工程: {path}")
            else:
                # 创建新文件
                path = PROJECTS_DIR / f"{current_project.name}_{int(time.time())}.json"
                current_project_path = str(path)
                is_overwrite = False
                logger.info(f"✨ 创建新工程: {path}")
            
            logger.info(f"=" * 60)
            logger.info(f"保存工程")
            logger.info(f"  工程名: {current_project.name}")
            logger.info(f"  保存路径: {path}")
            logger.info(f"  目录存在: {PROJECTS_DIR.exists()}")
            logger.info(f"  音频片段数: {len(current_project.audio_clips)}")
            logger.info(f"  BGM片段数: {len(current_project.bgm_clips)}")
            logger.info(f"  音效片段数: {len(current_project.sfx_clips)}")
            logger.info(f"  角色数: {len(current_project.characters)}")
            
            try:
                save_project_to_file(current_project, str(path))
                logger.info(f"✅ 工程已保存: {path}")
                logger.info(f"  文件大小: {os.path.getsize(path)} bytes")
                logger.info(f"{'=' * 60}")
                
                # 返回状态信息和隐藏确认区域
                if is_overwrite:
                    msg = f"✅ 已覆盖保存: {os.path.basename(path)}"
                else:
                    msg = f"✅ 已创建新工程: {os.path.basename(path)}"
                
                # 刷新工程列表
                updated_projects = get_projects_list()
                hide_result = hide_confirm_dialog(save_confirm_row, save_warning_text)
                return *hide_result, msg, updated_projects
            except Exception as e:
                logger.error(f"❌ 保存失败: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise
        
        def cancel_save():
            """取消保存，隐藏确认区域"""
            import logging
            logger = logging.getLogger(__name__)
            logger.info("❌ 取消保存操作")
            return hide_confirm_dialog(save_confirm_row, save_warning_text)
        
        save_project_btn.click(prepare_save_project, None, [save_confirm_row, save_warning_text])
        confirm_save_btn.click(execute_save_project, None, [save_confirm_row, save_warning_text, project_status, projects_table])
        cancel_save_btn.click(cancel_save, None, [save_confirm_row, save_warning_text])
        
        def load_project(file=None):
            import logging
            logger = logging.getLogger(__name__)
            global current_project
            nonlocal current_project_path  # 🔑 使用 nonlocal 访问外部变量
            
            logger.info(f"=" * 60)
            logger.info(f"加载工程")
            logger.info(f"  文件对象: {file}")
            logger.info(f"  文件类型: {type(file)}")
            
            if file is None:
                logger.warning("未选择文件")
                return [], DEFAULT_API_BASE, DEFAULT_API_KEY, DEFAULT_MODEL, [], gr.update(choices=[], value=None)
            
            # Gradio 6.x UploadButton 返回的是 UploadedFile 对象
            # 需要获取实际的文件路径
            if hasattr(file, 'name'):
                file_path = file.name
            elif hasattr(file, 'path'):
                file_path = file.path
            else:
                file_path = str(file)
            
            logger.info(f"  文件路径: {file_path}")
            logger.info(f"  文件存在: {os.path.exists(file_path)}")
            
            try:
                current_project = load_project_from_file(file_path)
                current_project_path = file_path  # 🔑 记录当前工程路径
                logger.info(f"✅ 工程已加载")
                logger.info(f"  工程名: {current_project.name}")
                logger.info(f"  音频片段数: {len(current_project.audio_clips)}")
                logger.info(f"  BGM片段数: {len(current_project.bgm_clips)}")
                logger.info(f"  音效片段数: {len(current_project.sfx_clips)}")
                logger.info(f"  角色数: {len(current_project.characters)}")
                
                # 恢复LLM配置到UI
                llm_cfg = current_project.llm_config
                api_base_val = llm_cfg.get("api_base", DEFAULT_API_BASE)
                api_key_val = llm_cfg.get("api_key", DEFAULT_API_KEY)
                model_val = llm_cfg.get("model", DEFAULT_MODEL)
                
                logger.info(f"  LLM API Base: {api_base_val}")
                logger.info(f"  LLM Model: {model_val}")
                logger.info(f"{'=' * 60}")
                
                # 🔑 刷新角色相关数据
                characters_data = refresh_characters_table()
                character_choices = get_character_choices()
                
                # 🔑 使用 gr.update() 来同时更新 choices 和清空 value
                character_dropdown_update = gr.update(
                    choices=character_choices,
                    value=None
                )
                
                return refresh_clips_table(), api_base_val, api_key_val, model_val, characters_data, character_dropdown_update
            except Exception as e:
                logger.error(f"❌ 加载失败: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise
        
        load_project_btn.upload(load_project, None, [clips_table, api_base, api_key, model, characters_table, clip_character])
        
        # 🔑 新建工程功能
        def new_project():
            """创建新工程"""
            import logging
            logger = logging.getLogger(__name__)
            global current_project
            nonlocal current_project_path
            
            logger.info("✨ 创建新工程")
            
            # 重置全局变量
            from .models import Project
            current_project = Project()
            current_project_path = None
            
            logger.info("✅ 新工程已创建")
            return [], "未命名", "", DEFAULT_API_BASE, DEFAULT_API_KEY, DEFAULT_MODEL, [], gr.update(choices=[], value=None)
        
        new_project_btn.click(new_project, None, [clips_table, project_name, input_text, api_base, api_key, model, characters_table, clip_character])
        
        # 工程文件列表管理
        def get_projects_list():
            """获取所有工程文件列表，带详细信息"""
            import logging
            logger = logging.getLogger(__name__)
            
            if not PROJECTS_DIR.exists():
                logger.warning(f"工程目录不存在: {PROJECTS_DIR}")
                return []
            
            # 获取所有 JSON 文件
            json_files = list(PROJECTS_DIR.glob("*.json"))
            if not json_files:
                logger.info("没有找到工程文件")
                return []
            
            # 按修改时间排序，最新的在前
            json_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 构建表格数据
            data = []
            for i, f in enumerate(json_files):
                stat = f.stat()
                # 格式化修改时间
                import datetime
                mod_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                # 格式化文件大小
                size_kb = stat.st_size / 1024
                if size_kb < 1024:
                    size_str = f"{size_kb:.1f} KB"
                else:
                    size_str = f"{size_kb/1024:.1f} MB"
                
                # 第一行标记为选中（最新工程）
                selected_mark = "▶" if i == 0 else ""
                
                data.append([
                    selected_mark,      # 选中标记
                    f.name,             # 工程名称
                    mod_time,           # 修改时间
                    size_str            # 文件大小
                ])
            
            logger.info(f"✅ 找到 {len(data)} 个工程文件")
            return data
        
        def refresh_projects_table():
            """刷新工程列表表格"""
            return get_projects_list()
        
        # 绑定工程管理事件
        
        def on_project_table_select(evt: gr.SelectData):
            """记录选中的工程行索引"""
            if evt.index:
                return evt.index[0]
            return -1
        
        projects_table.select(on_project_table_select, None, selected_project_index)
        
        def load_selected_project(row_index):
            """加载选中的工程"""
            import logging
            logger = logging.getLogger(__name__)
            nonlocal current_project_path
            
            row_idx = int(row_index)
            if row_idx < 0:
                raise gr.Error("❌ 请先在列表中选择一个工程")
            
            # 获取所有工程列表
            projects_data = get_projects_list()
            if row_idx >= len(projects_data):
                raise gr.Error("❌ 选中的工程不存在")
            
            file_name = projects_data[row_idx][1]  # 第二列是文件名
            
            file_path = PROJECTS_DIR / file_name
            if not file_path.exists():
                raise gr.Error(f"文件不存在: {file_path}")
            
            logger.info(f"📂 加载工程: {file_name}")
            
            global current_project
            try:
                current_project = load_project_from_file(str(file_path))
                current_project_path = str(file_path)
                logger.info(f"✅ 工程已加载")
                logger.info(f"  工程名: {current_project.name}")
                logger.info(f"  音频片段数: {len(current_project.audio_clips)}")
                logger.info(f"  角色数: {len(current_project.characters)}")
                
                # 恢复LLM配置到UI
                llm_cfg = current_project.llm_config
                api_base_val = llm_cfg.get("api_base", DEFAULT_API_BASE)
                api_key_val = llm_cfg.get("api_key", DEFAULT_API_KEY)
                model_val = llm_cfg.get("model", DEFAULT_MODEL)
                
                # 🔑 刷新角色相关数据
                characters_data = refresh_characters_table()
                character_choices = get_character_choices()
                
                # 🔑 使用 gr.update() 来同时更新 choices 和清空 value
                character_dropdown_update = gr.update(
                    choices=character_choices,
                    value=None
                )
                
                # 🔑 刷新表格，高亮当前加载的工程
                updated_projects_data = get_projects_list()
                for row in updated_projects_data:
                    if row[1] == file_name:
                        row[0] = "▶"
                    else:
                        row[0] = ""
                
                msg = f"✅ 已加载工程: {file_name}"
                logger.info(msg)
                
                # 返回：clips_table, project_name, input_text, api_base, api_key, model, characters_table, clip_character, projects_table, project_status
                return (
                    refresh_clips_table(), 
                    current_project.name, 
                    current_project.raw_text, 
                    api_base_val, 
                    api_key_val, 
                    model_val, 
                    characters_data, 
                    character_dropdown_update,
                    updated_projects_data,
                    msg
                )
            except Exception as e:
                logger.error(f"❌ 加载失败: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise
        
        def delete_selected_project(row_index):
            """点击删除按钮，显示确认对话框"""
            import logging
            logger = logging.getLogger(__name__)
            
            row_idx = int(row_index)
            if row_idx < 0:
                raise gr.Error("❌ 请先在列表中选择一个工程")
            
            # 获取所有工程列表
            projects_data = get_projects_list()
            if row_idx >= len(projects_data):
                raise gr.Error("❌ 选中的工程不存在")
            
            file_name = projects_data[row_idx][1]  # 第二列是文件名
            
            # 🔑 显示警告信息和确认按钮
            warning_msg = f"⚠️ 确定要删除该工程吗？此操作不可恢复！<br><br>📁 <b>{file_name}</b>"
            logger.info(f"🗑️ 请求删除工程: {file_name}（等待确认）")
            return show_confirm_dialog(delete_confirm_row, delete_warning_text, warning_msg)
        
        def confirm_delete_project(row_index):
            """确认删除工程"""
            import logging
            logger = logging.getLogger(__name__)
            nonlocal current_project_path
            
            row_idx = int(row_index)
            if row_idx < 0:
                raise gr.Error("❌ 请先在列表中选择一个工程")
            
            # 获取所有工程列表
            projects_data = get_projects_list()
            if row_idx >= len(projects_data):
                raise gr.Error("❌ 选中的工程不存在")
            
            file_name = projects_data[row_idx][1]  # 第二列是文件名
            
            file_path = PROJECTS_DIR / file_name
            if not file_path.exists():
                raise gr.Error(f"文件不存在: {file_path}")
            
            logger.info(f"🗑️ 确认删除工程: {file_name}")
            
            try:
                os.remove(str(file_path))
                logger.info(f"✅ 已删除: {file_path}")
                
                # 如果删除的是当前工程，重置路径
                if current_project_path and str(file_path) == current_project_path:
                    current_project_path = None
                    logger.info("  ℹ️ 已清除当前工程路径")
                
                # 刷新列表
                updated_projects_data = get_projects_list()
                msg = f"✅ 已删除工程: {file_name}"
                logger.info(msg)
                
                # 隐藏确认区域
                hide_result = hide_confirm_dialog(delete_confirm_row, delete_warning_text)
                return updated_projects_data, msg, *hide_result  # 只需要前两个返回值
            except Exception as e:
                logger.error(f"❌ 删除失败: {e}")
                raise gr.Error(f"删除失败: {e}")
        
        def cancel_delete():
            """取消删除，隐藏确认区域"""
            import logging
            logger = logging.getLogger(__name__)
            logger.info("❌ 取消删除操作")
            return hide_confirm_dialog(delete_confirm_row, delete_warning_text)
        
        # 绑定工程管理事件
        refresh_projects_btn.click(refresh_projects_table, None, projects_table)
        load_selected_btn.click(load_selected_project, [selected_project_index], [
            clips_table, project_name, input_text, api_base, api_key, model, 
            characters_table, clip_character, projects_table, project_status
        ])
        # 🔑 删除按钮：显示确认区域
        delete_selected_btn.click(delete_selected_project, [selected_project_index], [
            delete_confirm_row, delete_warning_text
        ])
        # 🔑 确认删除按钮：执行删除并隐藏确认区域
        confirm_delete_btn.click(confirm_delete_project, [selected_project_index], [
            projects_table, project_status, delete_confirm_row, delete_warning_text
        ])
        # 🔑 取消按钮：隐藏确认区域
        cancel_delete_btn.click(cancel_delete, None, [
            delete_confirm_row, delete_warning_text
        ])
        
        def clear_all():
            current_project.raw_text = ""
            current_project.script_lines = []
            current_project.audio_clips = []
            return "", []
        
        clear_btn.click(clear_all, None, [input_text, clips_table])
        
        # ==================== 角色管理 ====================
        
        def refresh_characters_table():
            """刷新角色列表表格"""
            import logging
            logger = logging.getLogger(__name__)
            
            if not current_project.characters:
                logger.info("ℹ️ 角色列表为空")
                return []
            
            data = []
            for i, char in enumerate(current_project.characters):
                # 获取音色的显示名称
                voice_display = next((v[0] for v in VOICE_OPTIONS if v[1] == char.voice_id), char.voice_id)
                personality_short = char.personality[:20] + "..." if len(char.personality) > 20 else char.personality
                data.append([
                    "",  # 选中标记（初始为空）
                    char.name,
                    voice_display,
                    char.rate,
                    char.pitch,
                    personality_short
                ])
            
            logger.info(f"✅ 刷新角色列表: {len(data)} 个角色")
            return data
        
        def add_new_character():
            """初始化新角色表单"""
            return "", "zh-CN-YunjianNeural", 0, 0, 1.0, "", "", "", "male", "", "", "💡 请填写角色信息后点击保存"
        
        def prepare_save_character(name, voice_id, rate, pitch, volume, personality, description, age, gender, emotion_style, notes):
            """准备保存角色，检查是否需要二次确认"""
            import logging
            logger = logging.getLogger(__name__)
            
            if not name or not name.strip():
                raise gr.Error("❌ 角色名称不能为空")
            
            name = name.strip()
            
            # 检查是否已存在同名角色
            existing = next((c for c in current_project.characters if c.name == name), None)
            
            if existing:
                # 存在同名角色，显示确认区域
                logger.info(f"⚠️ 检测到同名角色: {name}，等待确认")
                warning_msg = f"⚠️ 角色已存在，是否覆盖保存？<br><br>🎭 <b>{name}</b><br>⚠️ 现有角色的所有配置将被替换！"
                show_result = show_confirm_dialog(char_confirm_row, char_warning_text, warning_msg)
                return (
                    *show_result,
                    # 返回原值，等待用户确认
                    name, voice_id, rate, pitch, volume, personality, description, age, gender, emotion_style, notes
                )
            else:
                # 无同名，直接保存
                logger.info(f"➕ 创建新角色: {name}")
                return execute_save_character(name, voice_id, rate, pitch, volume, personality, description, age, gender, emotion_style, notes)
        
        def execute_save_character(name, voice_id, rate, pitch, volume, personality, description, age, gender, emotion_style, notes):
            """执行保存角色操作"""
            import logging
            logger = logging.getLogger(__name__)
            
            name = name.strip()
            
            # 检查是否已存在同名角色
            existing = next((c for c in current_project.characters if c.name == name), None)
            
            if existing:
                # 更新现有角色
                logger.info(f"🔄 更新角色: {name}")
                existing.voice_id = voice_id
                existing.rate = f"{rate}%"
                existing.pitch = f"{pitch}Hz"
                existing.volume = volume
                existing.personality = personality
                existing.description = description
                existing.age = age
                existing.gender = gender
                existing.emotion_style = emotion_style
                existing.notes = notes
                msg = f"✅ 已更新角色：{name}"
            else:
                # 创建新角色
                logger.info(f"➕ 创建新角色: {name}")
                from .models import Character
                new_char = Character(
                    name=name,
                    voice_id=voice_id,
                    rate=f"{rate}%",
                    pitch=f"{pitch}Hz",
                    volume=volume,
                    personality=personality,
                    description=description,
                    age=age,
                    gender=gender,
                    emotion_style=emotion_style,
                    notes=notes
                )
                current_project.characters.append(new_char)
                msg = f"✅ 已创建角色：{name}"
            
            logger.info(msg)
            # 使用当前选中的行索引刷新表格
            current_selected_idx = int(selected_char_index.value) if hasattr(selected_char_index, 'value') else -1
            hide_result = hide_confirm_dialog(char_confirm_row, char_warning_text)
            return (
                msg,
                refresh_characters_table_with_selection(current_selected_idx),
                *hide_result
            )
        
        def cancel_char_operation():
            """取消角色操作，隐藏确认区域"""
            import logging
            logger = logging.getLogger(__name__)
            logger.info("❌ 取消角色操作")
            return hide_confirm_dialog(char_confirm_row, char_warning_text)
        
        def delete_character(selected_row):
            """删除选中的角色"""
            import logging
            logger = logging.getLogger(__name__)
            
            if selected_row is None or len(selected_row) == 0:
                raise gr.Error("❌ 请先在列表中选择一个角色")
            
            # Dataframe 返回的是 [[row_data]] 格式
            row_data = selected_row[0] if isinstance(selected_row[0], list) else selected_row
            char_name = row_data[1]  # 第1列是选中标记，第2列才是角色名
            
            # 查找并删除角色
            existing = next((c for c in current_project.characters if c.name == char_name), None)
            if not existing:
                raise gr.Error(f"❌ 未找到角色：{char_name}")
            
            current_project.characters.remove(existing)
            msg = f"✅ 已删除角色：{char_name}"
            logger.info(msg)
            
            # 使用当前选中的行索引刷新表格
            current_selected_idx = int(selected_char_index.value) if hasattr(selected_char_index, 'value') else -1
            return msg, refresh_characters_table_with_selection(current_selected_idx)
        
        def clear_character_form():
            """清空角色编辑表单"""
            return "", "zh-CN-YunjianNeural", 0, 0, 1.0, "", "", "", "male", "", ""
        
        def get_character_choices():
            """获取角色选择列表（用于对白编辑）"""
            if not current_project.characters:
                return []
            # 🔑 返回简单的字符串列表，不是元组
            return [c.name for c in current_project.characters]
        
        def on_character_selected(character_name):
            """当选择角色时，自动填充音色配置"""
            import logging
            logger = logging.getLogger(__name__)
            
            if not character_name:
                logger.warning("⚠️ 未选择角色")
                return "zh-CN-YunjianNeural", 0, 0, 1.0
            
            # 查找角色
            char = next((c for c in current_project.characters if c.name == character_name), None)
            if not char:
                logger.warning(f"⚠️ 未找到角色: {character_name}，自动创建")
                # 🔑 自动创建角色
                from .models import Character
                new_char = Character(
                    name=character_name,
                    voice_id="zh-CN-YunjianNeural",
                    rate="+0%",
                    pitch="+0Hz",
                    volume=1.0,
                    personality="",
                    description=f"自动创建的角色：{character_name}",
                    age="",
                    gender="",
                    emotion_style="",
                    notes=""
                )
                current_project.characters.append(new_char)
                logger.info(f"✅ 已自动创建角色: {character_name}")
                
                # 🔑 刷新UI
                characters_data = refresh_characters_table()
                character_choices = get_character_choices()
                
                # 注意：这里无法直接更新clip_character的choices，需要在调用方处理
                return "zh-CN-YunjianNeural", 0, 0, 1.0
            
            logger.info(f"✅ 选择角色: {char.name}, 音色: {char.voice_id}")
            
            # 🔑 关键：将带单位的字符串转换为数字
            rate_str = str(char.rate).replace('%', '').strip()
            pitch_str = str(char.pitch).replace('Hz', '').strip()
            try:
                rate = int(rate_str) if rate_str else 0
                pitch = int(pitch_str) if pitch_str else 0
            except ValueError:
                rate = 0
                pitch = 0
            
            return char.voice_id, rate, pitch, char.volume
        
        # 绑定角色管理事件
        
        def on_char_table_select(evt: gr.SelectData):
            """记录选中的角色行索引并填充表单"""
            import logging
            logger = logging.getLogger(__name__)
            
            if not evt.index:
                logger.warning("⚠️ 未选中任何行")
                return -1, "", "zh-CN-YunjianNeural", 0, 0, 1.0, "", "", "", "male", "", ""
            
            row_idx = evt.index[0]
            logger.info(f"📋 选中角色行: {row_idx}")
            
            # 获取选中的角色信息
            if row_idx < 0 or row_idx >= len(current_project.characters):
                logger.warning(f"⚠️ 行索引超出范围: {row_idx}")
                return -1, "", "zh-CN-YunjianNeural", 0, 0, 1.0, "", "", "", "male", "", ""
            
            char = current_project.characters[row_idx]
            logger.info(f"✅ 加载角色信息: {char.name}")
            
            # 🔑 关键：将带单位的字符串转换为数字
            rate_str = str(char.rate).replace('%', '').strip()
            pitch_str = str(char.pitch).replace('Hz', '').strip()
            try:
                rate = int(rate_str) if rate_str else 0
                pitch = int(pitch_str) if pitch_str else 0
            except ValueError:
                rate = 0
                pitch = 0
            
            return (
                row_idx,
                char.name,
                char.voice_id,
                rate,
                pitch,
                char.volume,
                char.personality,
                char.description,
                char.age,
                char.gender if char.gender else "male",
                char.emotion_style,
                char.notes
            )
        
        def on_char_row_index_change(row_idx):
            """当选中角色行变化时，刷新表格显示高亮"""
            return refresh_characters_table_with_selection(int(row_idx))
        
        def load_character_to_form(selected_idx):
            """将选中角色的信息加载到表单"""
            import logging
            logger = logging.getLogger(__name__)
            
            selected_idx = int(selected_idx)
            if selected_idx < 0 or selected_idx >= len(current_project.characters):
                logger.warning(f"⚠️ 无效的行索引: {selected_idx}")
                return "", "zh-CN-YunjianNeural", 0, 0, 1.0, "", "", "", "male", "", ""
            
            char = current_project.characters[selected_idx]
            logger.info(f"📝 加载角色到表单: {char.name}")
            
            # 转换率和音调为数字
            rate_str = str(char.rate).replace('%', '').strip()
            pitch_str = str(char.pitch).replace('Hz', '').strip()
            try:
                rate = int(rate_str) if rate_str else 0
                pitch = int(pitch_str) if pitch_str else 0
            except ValueError:
                rate = 0
                pitch = 0
            
            return (
                char.name,
                char.voice_id,
                rate,
                pitch,
                char.volume,
                char.personality,
                char.description,
                char.age,
                char.gender if char.gender else "male",
                char.emotion_style,
                char.notes
            )
        
        def refresh_characters_table_with_selection(selected_idx=-1):
            """刷新角色表格，支持高亮选中行（6列结构）"""
            import logging
            logger = logging.getLogger(__name__)
            
            if not current_project.characters:
                logger.info("ℹ️ 角色列表为空")
                return []
            
            data = []
            for i, char in enumerate(current_project.characters):
                # 获取音色的显示名称
                voice_display = next((v[0] for v in VOICE_OPTIONS if v[1] == char.voice_id), char.voice_id)
                personality_short = char.personality[:20] + "..." if len(char.personality) > 20 else char.personality
                # 高亮选中行：在独立的第一列显示 ▶
                selected_mark = "▶" if i == selected_idx else ""
                data.append([
                    selected_mark,                    # 第1列：选中标记
                    char.name,                      # 第2列：角色名
                    voice_display,                  # 第3列：音色
                    char.rate,                      # 第4列：语速
                    char.pitch,                     # 第5列：音调
                    personality_short               # 第6列：性格摘要
                ])
            
            logger.info(f"✅ 刷新角色列表: {len(data)} 个角色")
            return data
        
        characters_table.select(on_char_table_select, None, [
            selected_char_index,
            char_name_input, char_voice_input, char_rate_input, char_pitch_input,
            char_volume_input, char_personality_input, char_description_input,
            char_age_input, char_gender_input, char_emotion_style_input, char_notes_input
        ])
        selected_char_index.change(on_char_row_index_change, [selected_char_index], characters_table)
        
        refresh_chars_btn.click(refresh_characters_table_with_selection, None, characters_table)
        add_char_btn.click(add_new_character, None, [
            char_name_input, char_voice_input, char_rate_input, char_pitch_input, 
            char_volume_input, char_personality_input, char_description_input, 
            char_age_input, char_gender_input, char_emotion_style_input, char_notes_input,
            char_status
        ])
        save_char_btn.click(prepare_save_character, [
            char_name_input, char_voice_input, char_rate_input, char_pitch_input,
            char_volume_input, char_personality_input, char_description_input,
            char_age_input, char_gender_input, char_emotion_style_input, char_notes_input
        ], [
            char_confirm_row, char_warning_text,
            char_name_input, char_voice_input, char_rate_input, char_pitch_input,
            char_volume_input, char_personality_input, char_description_input,
            char_age_input, char_gender_input, char_emotion_style_input, char_notes_input
        ])
        # 🔑 确认覆盖按钮：执行保存并隐藏确认区域
        confirm_char_btn.click(execute_save_character, [
            char_name_input, char_voice_input, char_rate_input, char_pitch_input,
            char_volume_input, char_personality_input, char_description_input,
            char_age_input, char_gender_input, char_emotion_style_input, char_notes_input
        ], [char_status, characters_table, char_confirm_row, char_warning_text])
        # 🔑 取消按钮：隐藏确认区域
        cancel_char_btn.click(cancel_char_operation, None, [
            char_confirm_row, char_warning_text
        ])
        delete_char_btn.click(delete_character, [characters_table], [char_status, characters_table])
        clear_char_form_btn.click(clear_character_form, None, [
            char_name_input, char_voice_input, char_rate_input, char_pitch_input,
            char_volume_input, char_personality_input, char_description_input,
            char_age_input, char_gender_input, char_emotion_style_input, char_notes_input
        ])
        
        # 🔑 对白编辑中的角色选择事件
        clip_character.change(on_character_selected, [clip_character], [clip_voice, clip_rate, clip_pitch, clip_volume])
        
        # 🔑 快捷管理角色按钮
        def quick_manage_characters():
            """快捷跳转到角色管理"""
            import logging
            logger = logging.getLogger(__name__)
            logger.info("🎭 点击了管理角色按钮")
            hint_text = """
> 💡 **请切换到【⚙️ 工程与配置】页签 -> 【🎭 角色管理】面板进行角色管理**
"""
            return gr.update(value=hint_text, visible=True), "💡 已显示角色管理指引"
        
        manage_chars_btn.click(quick_manage_characters, None, [char_manage_hint, editor_status])
        
        # ==================== 多音字与语气标记编辑器 ====================
        
        def ensure_voice_in_choices(voice):
            """确保音色值在下拉框的 choices 中，如果不在则返回默认值"""
            from .config import VOICE_IDS  # 🔑 在函数内部导入
            if voice in VOICE_IDS:
                return voice
            # 如果不在列表中，尝试匹配相似的音色
            for vid in VOICE_IDS:
                if voice and voice.startswith(vid.split('-')[0] + '-' + vid.split('-')[1]):
                    return vid
            # 否则返回默认值
            return "zh-CN-YunjianNeural"
        
        def update_original_text_display(row_index):
            """当选中行时，更新 SSML 文本显示和详细属性"""
            import logging
            logger = logging.getLogger(__name__)
            
            row_idx = int(row_index)
            logger.info(f"=" * 60)
            logger.info(f"加载对白属性 (行 {row_idx})")
            
            if row_idx < 0 or row_idx >= len(current_project.audio_clips):
                logger.warning(f"  ⚠️ 行索引越界: {row_idx}")
                return "", None, "zh-CN-YunjianNeural", 0, 0, 1.0
            
            clip = current_project.audio_clips[row_idx]
            logger.info(f"  Clip ID: {clip.id}")
            logger.info(f"  Clip 角色: {clip.character}")
            logger.info(f"  Clip 文本: {clip.text[:30]}...")
            logger.info(f"  Clip SSML: {getattr(clip, 'ssml_text', '')[:50]}...")
            
            # 查找对应的 script_line
            line = next((l for l in current_project.script_lines 
                        if l.text == clip.text and l.character == clip.character), None)
            
            if line:
                logger.info(f"  ✅ 找到匹配的 ScriptLine")
                ssml_text = getattr(line, 'ssml_text', '')  # 兼容旧工程
                voice = ensure_voice_in_choices(line.voice)  # 🔑 确保音色在 choices 中
                # 🔑 关键：将带单位的字符串转换为数字
                rate_str = str(line.rate).replace('%', '').strip()
                pitch_str = str(line.pitch).replace('Hz', '').strip()
                try:
                    rate = int(rate_str) if rate_str else 0
                    pitch = int(pitch_str) if pitch_str else 0
                except ValueError:
                    rate = 0
                    pitch = 0
                volume = getattr(line, 'volume', 1.0)  # 兼容旧工程，默认值 1.0
                logger.info(f"  Line SSML: {ssml_text[:50]}...")
                logger.info(f"  解析后的参数: voice={voice}, rate={rate}, pitch={pitch}, volume={volume}")
            else:
                logger.warning(f"  ⚠️ 未找到匹配的 ScriptLine，使用 Clip 数据")
                ssml_text = getattr(clip, 'ssml_text', '')  # 兼容旧工程
                voice = ensure_voice_in_choices(clip.voice)  # 🔑 确保音色在 choices 中
                # 🔑 关键：将带单位的字符串转换为数字
                rate_str = str(clip.rate).replace('%', '').strip()
                pitch_str = str(clip.pitch).replace('Hz', '').strip()
                try:
                    rate = int(rate_str) if rate_str else 0
                    pitch = int(pitch_str) if pitch_str else 0
                except ValueError:
                    rate = 0
                    pitch = 0
                volume = clip.volume
            
            # 如果没有 SSML 文本，使用普通文本
            if not ssml_text:
                logger.info(f"  ℹ️ SSML 为空，使用原始文本")
                ssml_text = clip.text
            
            # 🔑 检查是否有匹配的角色
            character_name = None
            if clip.character and current_project.characters:
                matching_char = next((c for c in current_project.characters if c.name == clip.character), None)
                if matching_char:
                    character_name = matching_char.name
                    logger.info(f"  ✅ 找到匹配的角色: {character_name}")
            
            logger.info(f"  📤 返回 SSML 长度: {len(ssml_text)}")
            logger.info(f"{'=' * 60}")
            
            return ssml_text, character_name, voice, rate, pitch, volume
        
        clips_table.select(
            update_original_text_display, 
            [selected_row_index], 
            [ssml_text_display, clip_character, clip_voice, clip_rate, clip_pitch, clip_volume]
        )
        
        def apply_clip_properties(row_index, character_name, voice, rate, pitch, volume, ssml_text):
            """应用选中的对白属性（包括 SSML 文本）"""
            import logging
            logger = logging.getLogger(__name__)
            
            try:
                row_idx = int(row_index)
                logger.info(f"=" * 60)
                logger.info(f"应用对白属性")
                logger.info(f"  行索引: {row_idx} (类型: {type(row_index)})")
                logger.info(f"  总片段数: {len(current_project.audio_clips)}")
                logger.info(f"  角色: {character_name}")
                logger.info(f"  SSML文本长度: {len(ssml_text)}")
                logger.info(f"  SSML文本预览: {ssml_text[:50]}...")
                
                if row_idx < 0 or row_idx >= len(current_project.audio_clips):
                    error_msg = f"❌ 行索引越界: {row_idx} (有效范围: 0-{len(current_project.audio_clips)-1})"
                    logger.error(error_msg)
                    return error_msg, refresh_clips_table(row_idx)
                
                clip = current_project.audio_clips[row_idx]
                logger.info(f"  Clip ID: {clip.id}")
                logger.info(f"  Clip 角色: {clip.character}")
                logger.info(f"  Clip 原文本: {clip.text[:30]}...")
                logger.info(f"  Clip 原SSML: {getattr(clip, 'ssml_text', '')[:30]}...")
                
                # 🔑 如果选择了角色，更新角色名称
                if character_name:
                    clip.character = character_name
                    logger.info(f"  ✅ 设置角色: {character_name}")
                
                # 查找对应的 script_line
                line = next((l for l in current_project.script_lines 
                            if l.text == clip.text and l.character == clip.character), None)
                
                if line:
                    logger.info(f"  ✅ 找到匹配的 ScriptLine")
                    logger.info(f"  原 SSML: {getattr(line, 'ssml_text', '')[:30]}...")
                    line.voice = voice
                    # 确保 rate 和 pitch 有正确的符号前缀（Edge-TTS 要求）
                    line.rate = f"{rate:+d}%"
                    line.pitch = f"{pitch:+d}Hz"
                    line.volume = volume
                    line.ssml_text = ssml_text  # 保存 SSML 文本
                    logger.info(f"  新 SSML: {line.ssml_text[:30]}...")
                else:
                    logger.warning(f"  ⚠️ 未找到匹配的 ScriptLine")
                
                # 更新 clip 属性
                clip.voice = voice
                # 确保 rate 和 pitch 有正确的符号前缀（Edge-TTS 要求）
                clip.rate = f"{rate:+d}%"
                clip.pitch = f"{pitch:+d}Hz"
                clip.volume = volume
                clip.ssml_text = ssml_text  # 保存 SSML 文本
                
                logger.info(f"  Clip 新SSML: {clip.ssml_text[:30]}...")
                logger.info(f"✅ 属性应用成功")
                logger.info(f"{'=' * 60}")
                
                success_msg = f"✅ 已应用属性：角色={character_name or '无'}, 音色={voice}, 语速={rate}%, 音调={pitch}Hz, 音量={volume}"
                # 刷新表格，保持高亮
                return success_msg, refresh_clips_table(row_idx)
                
            except Exception as e:
                error_msg = f"❌ 应用失败: {str(e)}"
                logger.error(f"{error_msg}")
                import traceback
                logger.error(traceback.format_exc())
                # 即使失败也刷新表格
                return error_msg, refresh_clips_table(int(row_index) if row_index else -1)
        
        apply_clip_props_btn.click(
            apply_clip_properties,
            [selected_row_index, clip_character, clip_voice, clip_rate, clip_pitch, clip_volume, ssml_text_display],
            [editor_status, clips_table]
        )
        
        def add_phoneme_marker(ssml_text, selected_char, replacement):
            """添加多音字标记 - 只替换第一个出现的字符"""
            if not selected_char or not replacement:
                raise gr.Error("请指定待标注字和替换字")
            
            if len(selected_char) != 1 or len(replacement) != 1:
                raise gr.Error("待标注字和替换字都必须是单个汉字")
            
            # 检查原文本中是否包含该字
            if selected_char not in ssml_text:
                raise gr.Error(f"SSML文本中不包含 '{selected_char}'")
            
            # 🔑 关键：只替换第一个出现的字符，不是全部替换
            marked_text = ssml_text.replace(selected_char, f"[phoneme={replacement}]{selected_char}[/phoneme]", 1)
            
            return marked_text, f"✅ 已标注：'{selected_char}' → '{replacement}'（仅替换第1个）"
        
        add_phoneme_btn.click(
            add_phoneme_marker,
            [ssml_text_display, phoneme_char_input, phoneme_replace_input],
            [ssml_text_display, editor_status]
        )
        
        def add_pause_marker(ssml_text, duration_ms):
            """插入停顿标记 - 在末尾添加"""
            pause_mark = f"[pause={int(duration_ms)}]"
            marked_text = ssml_text + pause_mark
            return marked_text, f"✅ 已插入 {duration_ms}ms 停顿"
        
        add_pause_btn.click(
            add_pause_marker,
            [ssml_text_display, pause_duration],
            [ssml_text_display, editor_status]
        )
        
        def add_emphasis_marker(ssml_text, preset, target_text, rate, pitch, volume):
            """添加强调标记 - 使用 <prosody> 标签包裹文本
            如果指定了 target_text，则只对该文本添加标记；否则对整个文本生效
            """
            # 预设参数映射（volume 必须使用百分比格式，如 +20%，不能是小数如 1.2）
            if preset == "slow_pause":
                prosody_text = f'<prosody rate="-20%" pitch="+5Hz" volume="+10%">{target_text or ssml_text}</prosody><pause=500>'
            else:
                prosody_text = f'<prosody rate="{params["rate"]}" pitch="{params["pitch"]}" volume="{params["volume"]}">{target_text or ssml_text}</prosody>'
            
            # 如果指定了目标文本，则在原文中查找并替换
            if target_text and target_text.strip():
                target = target_text.strip()
                if target in ssml_text:
                    new_text = ssml_text.replace(target, prosody_text, 1)
                    return new_text, f"✅ 已对目标文本添加{level_names.get(preset, preset)}标记", ""
                else:
                    # 目标文本不存在，追加到末尾
                    new_text = ssml_text + prosody_text
                    return new_text, f"⚠️ 未找到目标文本，已追加到末尾", ""
            else:
                # 未指定目标文本，对整个文本生效
                return prosody_text, f"✅ 已添加{level_names.get(preset, preset)}标记（整段）", ""
        
        add_emphasis_btn.click(
            add_emphasis_marker,
            [ssml_text_display, emphasis_preset, emphasis_target, emphasis_rate, emphasis_pitch, emphasis_volume],
            [ssml_text_display, editor_status, emphasis_target]
        )
        
        def on_emphasis_preset_change(preset):
            """当预设改变时，更新下方的 rate/pitch/volume 显示值"""
            presets = {
                "strong": {"rate": "-20%", "pitch": "+10Hz", "volume": "+20%"},
                "moderate": {"rate": "-10%", "pitch": "+5Hz", "volume": "+10%"},
                "reduced": {"rate": "+10%", "pitch": "-5Hz", "volume": "-10%"},
                "very_slow": {"rate": "-30%", "pitch": "+0Hz", "volume": "+15%"},
                "fast_excited": {"rate": "+40%", "pitch": "+20Hz", "volume": "+25%"},
                "low_pitch": {"rate": "+0%", "pitch": "-20Hz", "volume": "+10%"},
                "high_pitch": {"rate": "+0%", "pitch": "+30Hz", "volume": "+10%"},
                "slow_pause": {"rate": "-20%", "pitch": "+5Hz", "volume": "+10%"},
                "custom": {"rate": "-20%", "pitch": "+10Hz", "volume": "+20%"}  # custom 使用默认值
            }
            params = presets.get(preset, presets["strong"])
            # 提取数值，去掉单位
            def extract_numeric_value(param_val, param_type):
                if param_type == "rate" and param_val.endswith('%'):
                    return param_val[:-1]  # 去掉 % 符号
                elif param_type == "pitch" and param_val.endswith('Hz'):
                    return param_val[:-2]  # 去掉 Hz
                elif param_type == "volume" and param_val.endswith('%'):
                    return param_val[:-1]  # 去掉 % 符号
                return param_val
            
            rate_val = extract_numeric_value(params["rate"], "rate")
            pitch_val = extract_numeric_value(params["pitch"], "pitch")
            volume_val = extract_numeric_value(params["volume"], "volume")
            return rate_val, pitch_val, volume_val
        
        emphasis_preset.change(
            on_emphasis_preset_change,
            [emphasis_preset],
            [emphasis_rate, emphasis_pitch, emphasis_volume]
        )
        
        def clear_all_markers(ssml_text):
            """清除所有标记 - 恢复纯文本"""
            import re
            # 移除 <prosody> 标签，保留内容
            clean_text = re.sub(r'<prosody[^>]*>(.*?)</prosody>', r'\1', ssml_text, flags=re.DOTALL)
            # 移除 <pause> 标记
            clean_text = re.sub(r'<pause=\d+>', '', clean_text)
            # 移除 [phoneme] 标记，保留原字
            clean_text = re.sub(r'\[phoneme=[^\]]+\](.*?)\[/phoneme\]', r'\1', clean_text)
            return clean_text, "✅ 已清除所有标记，恢复纯文本"
        
        clear_markers_btn.click(
            clear_all_markers,
            [ssml_text_display],
            [ssml_text_display, editor_status]
        )
        
        async def preview_marked_text(ssml_text, row_index):
            """预听带标记的文本效果"""
            row_idx = int(row_index)
            if row_idx < 0 or row_idx >= len(current_project.audio_clips):
                raise gr.Error("请先选中一个片段")
            
            clip = current_project.audio_clips[row_idx]
            
            # 创建临时 ScriptLine，使用 SSML 文本
            from .models import ScriptLine
            temp_line = ScriptLine(
                type=clip.type,
                character=clip.character,
                emotion="",
                text=clip.text,  # 保留原始文本
                ssml_text=ssml_text,  # 使用 SSML 文本
                voice=clip.voice,
                rate=clip.rate,
                pitch=clip.pitch
            )
            
            # 生成临时音频
            import uuid
            temp_path = f"data/audio/temp_preview_{uuid.uuid4().hex[:8]}.mp3"
            
            try:
                await synthesize_single_line(temp_line, temp_path)
                return temp_path
            except Exception as e:
                raise gr.Error(f"预听失败: {str(e)}")
        
        preview_marked_btn.click(
            preview_marked_text,
            [ssml_text_display, selected_row_index],
            marked_audio_preview
        )
    
    # 注入自定义CSS
    demo.css = custom_css
    
    return demo
