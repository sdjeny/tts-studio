"""
三角色广播剧生成脚本（VoiceDesign 版本）
角色：旁白、主角（林轩）、配角（苏婉）
情感变化：喜、怒、哀、乐，但角色声音识别不丢失
模型路径：C:/Users/s/.cache/modelscope/hub/models/Qwen/Qwen3-TTS-12Hz-1___7B-VoiceDesign
"""
import os
import sys
import subprocess
import numpy as np
import soundfile as sf
import torch
import torchaudio

# ========== 0. 环境准备 ==========
try:
    import soundfile
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "soundfile", "-q"])
    import soundfile

# ========== 1. 加载模型（离线，CPU） ==========
model_path = r"C:\Users\s\.cache\huggingface\hub\models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice\snapshots\0c0e3051f131929182e2c023b9537f8b1c68adfe"

from qwen_tts import Qwen3TTSModel

print("正在加载模型（CPU）...")
model = Qwen3TTSModel.from_pretrained(
    model_path,
    device_map="cpu",
    torch_dtype=torch.float32,
    local_files_only=True
)
print("✅ 模型加载完成。\n")

# ========== 2. 定义角色的固定声音描述 ==========
role_to_speaker = {
    "旁白": "Uncle_Fu",
    "主角_林轩": "Dylan",
    "配角_苏婉": "Vivian"
}
CHARACTER_VOICES = {
    "旁白": {
        "voice_description": (
            "一位四十岁左右的男性专业旁白，声音沉稳、清晰、富有磁性。"
            "语调客观，不带个人情绪，像纪录片解说那样娓娓道来。"
            "语速中等偏慢，每个字都咬得很清楚。"
        )
    },
    "主角_林轩": {
        "voice_description": (
            "一位二十五岁的年轻男性，声音温暖有朝气，略带一点少年感。"
            "音色明亮，底气充足，说话时带着年轻人特有的活力。"
            "即使情绪变化，音色本身的质感保持不变。"
        )
    },
    "配角_苏婉": {
        "voice_description": (
            "一位二十三岁的年轻女性，声音清甜柔和，听感舒适。"
            "音色像春风一样轻软，但不失清晰度。"
            "即使愤怒或悲伤，声线的甜美本质也不会改变。"
        )
    }
}

# ========== 3. 编写三分钟剧本 ==========
script = [
    ("旁白", "夜幕降临，城市的灯火渐渐亮起。林轩独自站在天台上，望着远处出神。", "", "Chinese"),
    ("旁白", "他刚刚经历了一场激烈的争吵，心里五味杂陈。", "", "Chinese"),
    ("主角_林轩", "他们凭什么这样对我？我辛辛苦苦这么久，一句话就把我打发了？", "愤怒，语气强烈，语速稍快", "Chinese"),
    ("配角_苏婉", "林轩，你先冷静下来。我知道你很难过，但生气解决不了问题。", "温柔，关切，语速平缓", "Chinese"),
    ("主角_林轩", "不只是生气……我更多的是失望。我一直相信他们，没想到结果会是这样。", "悲伤，低落，语气沉重", "Chinese"),
    ("配角_苏婉", "失望是因为你在乎，这没有错。但你不能让这一次失败否定掉你的全部。", "温暖，鼓励，略带坚定", "Chinese"),
    ("旁白", "苏婉的话像一股暖流，缓缓流入林轩的心里。他沉默了片刻。", "", "Chinese"),
    ("主角_林轩", "你说的对。或许……是我太钻牛角尖了。只是，我真的不知道接下来该怎么走。", "语气缓和，带着一丝迷茫", "Chinese"),
    ("配角_苏婉", "还记得我们大学时一起做的那个项目吗？当时所有人都觉得我们不行，可最后呢？", "语气轻快，带着笑意，鼓励", "Chinese"),
    ("主角_林轩", "哈哈，那次啊……我们熬了整整三个通宵，你还差点把咖啡泼在电源上。", "开心，笑，放松", "Chinese"),
    ("配角_苏婉", "那就是青春啊！所以你看，摔倒了再爬起来，你从来都不是一个人。", "调皮，活泼，语速稍快", "Chinese"),
    ("旁白", "天台上，两个人的笑声冲淡了夜晚的寒意。有时候，一句简单的理解，就足以让阴霾散去。", "", "Chinese"),
    ("主角_林轩", "谢谢你，苏婉。我想我找到重新开始的方向了。明天，我会让他们看到不一样的我。", "坚定，充满希望，语速中等", "Chinese"),
    ("配角_苏婉", "这才是我认识的林轩。走吧，我请你喝杯热奶茶，庆祝你的新生。", "欣慰，温暖，带着小小的骄傲", "Chinese"),
    ("旁白", "灯光下，两个年轻人并肩走下天台，融进了城市的万家灯火中。", "", "Chinese"),
]

# ========== 4. 生成所有语音片段（每句独立保存） ==========
output_dir = "output_segments"
os.makedirs(output_dir, exist_ok=True)

sample_rate = None  # 记录第一个片段的采样率，后续片段若不一致则重采样

for idx, (role, text, instruct, lang) in enumerate(script):
    voice_desc = CHARACTER_VOICES[role]["voice_description"]

    print(f"[{idx+1}/{len(script)}] 生成 {role}：{text}...")

    wavs, sr = model.generate_custom_voice(
        text=text,
        language=lang,
        speaker=role_to_speaker[role],  # 直接指定角色！
        instruct=instruct               # instruct 继续生效，只控制情感
    )

    clip = wavs[0] if isinstance(wavs, list) else wavs

    # 统一采样率（若与首个片段不同则用 torchaudio 重采样）
    if sample_rate is None:
        sample_rate = sr
    elif sr != sample_rate:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=sample_rate)
        clip = torch.from_numpy(clip).unsqueeze(0)  # [1, samples]
        clip = resampler(clip).squeeze(0).numpy()
        sr = sample_rate

    # 生成清晰的文件名
    emotion_tag = instruct if instruct else "中性"
    # 去掉文件名中的非法字符，保留中英文、数字、空格、下划线、连字符
    safe_emotion = "".join(c for c in emotion_tag if c.isalnum() or c in (' ', '_', '-', '，'))
    filename = f"{idx+1:02d}_{role}_{safe_emotion}.wav"
    filepath = os.path.join(output_dir, filename)

    sf.write(filepath, clip, sr)
    print(f"   已保存: {filepath}")

print(f"\n✅ 全部生成完毕！共 {len(script)} 个文件，保存在 '{output_dir}/' 文件夹内。")