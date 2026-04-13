#!/bin/bash
# 确保在项目根目录执行（例如 /work/docker/tts-studio）

# 创建目录结构
mkdir -p app data

# ==================== app/__init__.py ====================
cat > app/__init__.py << 'EOF'
# 标识 app 为 Python 包
EOF

# ==================== app/config.py ====================
cat > app/config.py << 'EOF'
import os
from pathlib import Path

# 环境变量默认配置
DEFAULT_API_BASE = os.getenv("DEFAULT_API_BASE", "http://localhost:11434/v1")
DEFAULT_API_KEY = os.getenv("DEFAULT_API_KEY", "ollama")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen2.5:7b")

# 数据存储目录
DATA_DIR = Path("/app/data")
AUDIO_DIR = DATA_DIR / "audio"
PROJECTS_DIR = DATA_DIR / "projects"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)

# 音色配置
DEFAULT_VOICES = {
    "旁白": {"voice": "zh-CN-YunjianNeural", "rate": "-5%", "pitch": "+0Hz"},
    "默认男": {"voice": "zh-CN-YunxiNeural", "rate": "+0%", "pitch": "+0Hz"},
    "默认女": {"voice": "zh-CN-XiaoxiaoNeural", "rate": "+0%", "pitch": "+0Hz"},
}

VOICE_OPTIONS = [
    "zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural", "zh-CN-YunjianNeural",
    "zh-CN-YunxiNeural", "zh-CN-YunxiaNeural", "zh-CN-YunyangNeural",
    "zh-CN-XiaochenNeural", "zh-CN-XiaohanNeural", "zh-CN-XiaomengNeural",
]

# LLM 提示词
SYSTEM_PROMPT = """你是一个专业的剧本解析器。将输入文本转换为结构化的有声剧本格式。

规则：
1. 识别：人物对白、旁白、场景说明/动作描写。
2. 对白格式：若有情绪提示，提取到 emotion 字段（如"愤怒"、"低声"）。
3. 只输出纯 JSON 数组，不要 Markdown 代码块。

输出格式：
[
  {"type": "direction", "character": "", "emotion": "", "text": "场景：大殿内，夜。"},
  {"type": "narration", "character": "旁白", "emotion": "", "text": "这场权力的游戏..."},
  {"type": "dialogue", "character": "李远", "emotion": "隐忍", "text": "臣无话可说。"}
]"""
EOF

# ==================== app/models.py ====================
cat > app/models.py << 'EOF'
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class AudioClip:
    """音频片段（对白/音效/背景乐）"""
    id: str
    type: str                    # "dialogue", "bgm", "sfx"
    character: str               # 角色名
    text: str                    # 文本内容
    file_path: str               # 实际音频文件路径
    voice: str                   # 音色
    rate: str                    # 语速
    pitch: str                   # 音调
    volume: float = 1.0          # 音量倍数
    start_time: float = 0.0      # 开始时间（秒）
    duration: float = 0.0        # 时长（秒）
    is_generated: bool = False   # 是否已生成音频

@dataclass
class ScriptLine:
    """单行剧本（解析后的中间格式）"""
    type: str
    character: str
    emotion: str
    text: str
    voice: str
    rate: str
    pitch: str

@dataclass
class Project:
    """完整工程"""
    name: str
    raw_text: str = ""
    script_lines: List[ScriptLine] = field(default_factory=list)
    audio_clips: List[AudioClip] = field(default_factory=list)
    bgm_clips: List[AudioClip] = field(default_factory=list)
    sfx_clips: List[AudioClip] = field(default_factory=list)
    llm_config: Dict = field(default_factory=dict)
    character_voices: Dict = field(default_factory=dict)

# 全局当前工程
current_project = Project(name="未命名")
EOF

# ==================== app/llm_parser.py ====================
cat > app/llm_parser.py << 'EOF'
import json
import re
from typing import List, Dict
from openai import OpenAI
from .config import SYSTEM_PROMPT

def parse_with_llm(text: str, api_base: str, api_key: str, model: str) -> List[Dict]:
    client = OpenAI(base_url=api_base, api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    content = response.choices[0].message.content
    content = re.sub(r'^```json\s*|\s*```$', '', content.strip())
    return json.loads(content)
EOF

# ==================== app/tts_engine.py ====================
cat > app/tts_engine.py << 'EOF'
import os
import edge_tts
from pydub import AudioSegment
from pydub.generators import Sine
import uuid
from typing import List
from .models import AudioClip, ScriptLine
from .config import AUDIO_DIR

async def synthesize_single_line(line: ScriptLine, output_path: str) -> float:
    """合成单行，返回音频时长（秒）"""
    if not line.text.strip():
        return 0.0
    
    prosody_attrs = []
    if line.rate:
        prosody_attrs.append(f'rate="{line.rate}"')
    if line.pitch:
        prosody_attrs.append(f'pitch="{line.pitch}"')
    
    content = line.text
    if prosody_attrs:
        content = f'<prosody {" ".join(prosody_attrs)}>{content}</prosody>'
    
    ssml = f"""
    <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
        <voice name="{line.voice}">
            {content}
        </voice>
    </speak>
    """
    
    communicate = edge_tts.Communicate(ssml, line.voice)
    await communicate.save(output_path)
    
    audio = AudioSegment.from_mp3(output_path)
    return audio.duration_seconds

def mix_audio_tracks(clips: List[AudioClip], total_duration: float = None) -> str:
    """将多个 AudioClip 按时间轴混合，返回最终音频路径"""
    if not clips:
        return None
    
    max_end = 0.0
    valid_clips = []
    for clip in clips:
        if clip.is_generated and os.path.exists(clip.file_path):
            audio = AudioSegment.from_mp3(clip.file_path)
            if clip.volume != 1.0:
                audio = audio + (20 * (clip.volume - 1))
            clip._audio_segment = audio
            clip._start_ms = int(clip.start_time * 1000)
            clip._end_ms = clip._start_ms + len(audio)
            max_end = max(max_end, clip._end_ms)
            valid_clips.append(clip)
    
    if total_duration is None:
        total_duration = max_end / 1000.0
    
    canvas = AudioSegment.silent(duration=int(total_duration * 1000) + 500)
    
    for clip in valid_clips:
        canvas = canvas.overlay(clip._audio_segment, position=clip._start_ms)
        del clip._audio_segment
    
    output_path = AUDIO_DIR / f"final_mix_{uuid.uuid4().hex[:8]}.mp3"
    canvas.export(output_path, format="mp3")
    return str(output_path)

def generate_silence(duration_sec: float) -> str:
    """生成静音文件（用于占位）"""
    path = AUDIO_DIR / f"silence_{uuid.uuid4().hex[:8]}.mp3"
    AudioSegment.silent(duration=int(duration_sec * 1000)).export(path, format="mp3")
    return str(path)

def generate_tone(freq: int = 440, duration_sec: float = 1.0) -> str:
    """生成测试音（用于音效占位）"""
    path = AUDIO_DIR / f"tone_{uuid.uuid4().hex[:8]}.mp3"
    Sine(freq).to_audio_segment(duration=int(duration_sec * 1000)).export(path, format="mp3")
    return str(path)
EOF

# ==================== app/project_manager.py ====================
cat > app/project_manager.py << 'EOF'
import json
import os
import uuid
from dataclasses import asdict
from typing import List
from .models import Project, ScriptLine, AudioClip
from .config import AUDIO_DIR

def script_lines_to_clips(lines: List[ScriptLine]) -> List[AudioClip]:
    """将剧本行转换为音频片段（尚未生成）"""
    clips = []
    for i, line in enumerate(lines):
        if line.type in ("dialogue", "narration") and line.text.strip():
            clip = AudioClip(
                id=uuid.uuid4().hex[:8],
                type="dialogue",
                character=line.character,
                text=line.text,
                file_path=str(AUDIO_DIR / f"clip_{i:04d}_{uuid.uuid4().hex[:4]}.mp3"),
                voice=line.voice,
                rate=line.rate,
                pitch=line.pitch,
                volume=1.0,
                start_time=sum(c.duration for c in clips) if clips else 0.0,
                duration=0.0,
                is_generated=False
            )
            clips.append(clip)
    return clips

def load_project_from_file(path: str) -> Project:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    p = Project(name=data.get("name", "未命名"))
    p.raw_text = data.get("raw_text", "")
    p.script_lines = [ScriptLine(**l) for l in data.get("script_lines", [])]
    p.llm_config = data.get("llm_config", {})
    p.character_voices = data.get("character_voices", {})
    
    for c in data.get("audio_clips", []):
        clip = AudioClip(**c)
        clip.is_generated = os.path.exists(clip.file_path)
        p.audio_clips.append(clip)
    for c in data.get("bgm_clips", []):
        clip = AudioClip(**c)
        clip.is_generated = os.path.exists(clip.file_path)
        p.bgm_clips.append(clip)
    for c in data.get("sfx_clips", []):
        clip = AudioClip(**c)
        clip.is_generated = os.path.exists(clip.file_path)
        p.sfx_clips.append(clip)
    
    return p

def save_project_to_file(project: Project, path: str):
    data = {
        "name": project.name,
        "raw_text": project.raw_text,
        "script_lines": [asdict(l) for l in project.script_lines],
        "audio_clips": [asdict(c) for c in project.audio_clips],
        "bgm_clips": [asdict(c) for c in project.bgm_clips],
        "sfx_clips": [asdict(c) for c in project.sfx_clips],
        "llm_config": project.llm_config,
        "character_voices": project.character_voices
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
EOF

# ==================== app/ui.py ====================
cat > app/ui.py << 'EOF'
import gradio as gr
import asyncio
import os
import time
import uuid
from pydub import AudioSegment
from .models import current_project, ScriptLine, AudioClip
from .config import DEFAULT_API_BASE, DEFAULT_API_KEY, DEFAULT_MODEL, DEFAULT_VOICES, PROJECTS_DIR
from .llm_parser import parse_with_llm
from .tts_engine import synthesize_single_line, mix_audio_tracks
from .project_manager import script_lines_to_clips, load_project_from_file, save_project_to_file

def build_ui():
    with gr.Blocks(title="多轨剧本配音工作台", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🎛️ 多轨剧本配音工作台")
        project_state = gr.State(current_project)
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📁 工程")
                project_name = gr.Textbox(label="工程名", value="未命名")
                with gr.Row():
                    save_project_btn = gr.Button("💾 保存", size="sm")
                    load_project_btn = gr.UploadButton("📂 加载", file_types=[".json"], size="sm")
                export_audio_btn = gr.Button("📤 导出混音", variant="primary")
                
                gr.Markdown("### ⚙️ LLM 配置")
                api_base = gr.Textbox(label="API Base", value=DEFAULT_API_BASE)
                api_key = gr.Textbox(label="API Key", value=DEFAULT_API_KEY, type="password")
                model = gr.Textbox(label="模型", value=DEFAULT_MODEL)
                
                gr.Markdown("### 🎵 背景乐/音效")
                with gr.Accordion("添加音轨", open=False):
                    bgm_file = gr.Audio(label="上传背景乐", type="filepath")
                    bgm_volume = gr.Slider(0.0, 2.0, 0.3, label="背景乐音量")
                    add_bgm_btn = gr.Button("➕ 添加背景乐轨")
                    
                    sfx_name = gr.Textbox(label="音效名称", placeholder="敲门声")
                    sfx_file = gr.Audio(label="上传音效", type="filepath")
                    sfx_start = gr.Number(0.0, label="开始时间(秒)")
                    sfx_volume = gr.Slider(0.0, 2.0, 1.0, label="音量")
                    add_sfx_btn = gr.Button("➕ 添加音效轨")
            
            with gr.Column(scale=3):
                gr.Markdown("### 📝 输入文本")
                input_text = gr.Textbox(
                    label="粘贴小说或剧本",
                    placeholder="支持任意格式，LLM 会自动解析",
                    lines=6
                )
                with gr.Row():
                    parse_btn = gr.Button("🔍 LLM 解析", variant="primary")
                    clear_btn = gr.Button("🧹 清空")
                
                gr.Markdown("### 🎤 对白片段（双击编辑）")
                clips_table = gr.Dataframe(
                    headers=["ID", "角色", "文本", "音色", "语速", "音调", "音量", "开始时间(秒)", "状态"],
                    datatype=["str", "str", "str", "str", "str", "str", "number", "number", "str"],
                    label="可编辑的音频片段",
                    interactive=True,
                    row_count=(8, "dynamic"),
                )
                
                with gr.Row():
                    generate_selected_btn = gr.Button("🎙️ 生成选中片段")
                    preview_selected_btn = gr.Button("🔊 预听选中")
                    generate_all_btn = gr.Button("🎬 生成全部对白", variant="primary")
                
                gr.Markdown("### 🎚️ 混音输出")
                with gr.Row():
                    total_duration = gr.Number(0.0, label="总时长(秒), 0=自动")
                    mix_btn = gr.Button("🎧 合成混音", variant="primary", size="lg")
                final_audio = gr.Audio(label="成品混音", type="filepath")
        
        # 事件处理函数
        def update_project_name(name):
            current_project.name = name
            return f"工程名已更新: {name}"
        project_name.change(update_project_name, project_name, None)
        
        def refresh_clips_table():
            if not current_project.audio_clips:
                return []
            data = []
            for c in current_project.audio_clips:
                data.append([
                    c.id, c.character, c.text[:30] + "..." if len(c.text) > 30 else c.text,
                    c.voice, c.rate, c.pitch, c.volume, c.start_time,
                    "✅" if c.is_generated else "⏳"
                ])
            return data
        
        def parse_text(text, base, key, mdl):
            current_project.llm_config = {"api_base": base, "api_key": key, "model": mdl}
            current_project.raw_text = text
            parsed = parse_with_llm(text, base, key, mdl)
            lines = []
            for item in parsed:
                char = item.get("character", "")
                if item["type"] == "narration":
                    char = "旁白"
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
            return refresh_clips_table()
        
        parse_btn.click(parse_text, [input_text, api_base, api_key, model], [clips_table])
        
        async def generate_selected(evt: gr.SelectData):
            if evt.index is None:
                raise gr.Error("请先在表格中选中一行")
            clip = current_project.audio_clips[evt.index[0]]
            line = next((l for l in current_project.script_lines 
                       if l.text == clip.text and l.character == clip.character), None)
            if line:
                duration = await synthesize_single_line(line, clip.file_path)
                clip.duration = duration
                clip.is_generated = True
                for i in range(evt.index[0] + 1, len(current_project.audio_clips)):
                    current_project.audio_clips[i].start_time = (
                        current_project.audio_clips[i-1].start_time + current_project.audio_clips[i-1].duration
                    )
            return refresh_clips_table()
        
        clips_table.select(generate_selected, None, clips_table)
        
        async def generate_all():
            for clip in current_project.audio_clips:
                if not clip.is_generated:
                    line = next((l for l in current_project.script_lines 
                               if l.text == clip.text and l.character == clip.character), None)
                    if line:
                        duration = await synthesize_single_line(line, clip.file_path)
                        clip.duration = duration
                        clip.is_generated = True
            return refresh_clips_table()
        
        generate_all_btn.click(generate_all, None, clips_table)
        
        def preview_selected(evt: gr.SelectData):
            if evt.index is None:
                raise gr.Error("请先选中一行")
            clip = current_project.audio_clips[evt.index[0]]
            if clip.is_generated and os.path.exists(clip.file_path):
                return clip.file_path
            raise gr.Error("该片段尚未生成")
        
        preview_selected_btn.click(preview_selected, None, gr.Audio(label="预听", type="filepath"))
        
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
        
        def save_project():
            path = PROJECTS_DIR / f"{current_project.name}_{int(time.time())}.json"
            save_project_to_file(current_project, str(path))
            return str(path)
        
        save_project_btn.click(save_project, None, gr.File(label="工程文件"))
        
        def load_project(file=None):
            global current_project
            if file is None:
                return []
            current_project = load_project_from_file(file.name)
            return refresh_clips_table()
        
        load_project_btn.upload(load_project, None, clips_table)
        
        def clear_all():
            current_project.raw_text = ""
            current_project.script_lines = []
            current_project.audio_clips = []
            return "", []
        
        clear_btn.click(clear_all, None, [input_text, clips_table])
    
    return demo
EOF

# ==================== app/main.py ====================
cat > app/main.py << 'EOF'
from .ui import build_ui

if __name__ == "__main__":
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_api=False
    )
EOF

# ==================== Dockerfile ====================
cat > Dockerfile << 'EOF'
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libavcodec-extra \
        libavdevice-dev \
        libavfilter-dev \
        libavformat-dev \
        libavutil-dev \
        libpostproc-dev \
        libswresample-dev \
        libswscale-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "index-url = https://mirrors.aliyun.com/pypi/simple/" >> /root/.pip/pip.conf && \
    echo "trusted-host = mirrors.aliyun.com" >> /root/.pip/pip.conf

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

RUN mkdir -p /app/data/projects /app/data/audio /app/data/tmp

ARG UID=1000
ARG GID=1000

RUN addgroup --system --gid $GID appgroup && \
    adduser --system --uid $UID --gid $GID appuser && \
    chown -R appuser:appgroup /app

COPY app/ /app/app/

USER appuser

EXPOSE 7860

CMD ["python", "-m", "app.main"]
EOF

# ==================== docker-compose.yml ====================
cat > docker-compose.yml << 'EOF'
services:
  tts-studio:
    build:
      context: .
      args:
        UID: ${UID:-1000}
        GID: ${GID:-1000}
    container_name: tts-studio
    ports:
      - "7860:7860"
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env:ro
      - ./app:/app/app
    environment:
      - GRADIO_SERVER_NAME=0.0.0.0
      - GRADIO_SERVER_PORT=7860
      - DEFAULT_API_BASE=${DEFAULT_API_BASE:-http://192.168.0.77:11434/v1}
      - DEFAULT_API_KEY=${DEFAULT_API_KEY:-ollama}
      - DEFAULT_MODEL=${DEFAULT_MODEL:-deepseek-v3.1:671b-cloud}
      - TMPDIR=/app/data/tmp
      - MPLCONFIGDIR=/app/data/tmp/matplotlib
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
    healthcheck:
      test: ["CMD", "python", "-c", "import socket; s=socket.socket(); s.connect(('localhost',7860))"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
EOF

# ==================== requirements.txt ====================
cat > requirements.txt << 'EOF'
gradio>=5.0.0
edge-tts==6.1.14
openai==1.58.1
pydub==0.25.1
huggingface-hub==0.26.0
EOF

# ==================== .env 示例 ====================
cat > .env.example << 'EOF'
UID=1000
GID=1000
DEFAULT_API_BASE=http://192.168.0.77:11434/v1
DEFAULT_API_KEY=ollama
DEFAULT_MODEL=deepseek-v3.1:671b-cloud
EOF

echo "=========================================="
echo "所有文件已生成！"
echo "请执行以下命令创建 .env 文件："
echo "echo \"UID=\$(id -u)\" > .env"
echo "echo \"GID=\$(id -g)\" >> .env"
echo "=========================================="