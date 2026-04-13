"""
查看 phoneme 替换前后的完整 SSML 对比，并生成音频
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(__file__))

from app.tts_parser import preprocess_phoneme_markers
from edge_tts.communicate import mkssml
from edge_tts.data_classes import TTSConfig
from app.models import ScriptLine
from app.tts_engine import synthesize_single_line

# 原始文本（带 phoneme 标记）
original_text = (
    "[rate=-30%]那[phoneme=航]行[/phoneme][phoneme=掌]长[/phoneme][/rate]"
    "[pause=300]"
    "[pitch=+15Hz]竟然[phoneme=仲]重[/phoneme]新[/pitch]"
    "[rate=+20%]走进了那家[phoneme=月]乐[/phoneme]器店[/rate]"
    "[pause=200]"
    "[pitch=-10Hz]看着那些[phoneme=郝]好[/phoneme]玩的乐器[/pitch]"
    "[rate=-10%]他[phoneme=这]着[/phoneme]迷了[/rate]"
    "[pause=400]"
    "[pitch=+20Hz]突然！[/pitch]"
    "[rate=+30%]他发现了一个[phoneme=常]长[/phoneme][phoneme=虫]重[/phoneme]的箱子[/rate]"
    "[pause=500]"
    "[rate=-40%][pitch=-15Hz]里面...到底是什么呢？[/pitch][/rate]"
)

print("=" * 80)
print("📝 Phoneme 替换前后对比")
print("=" * 80)

print("\n【替换前 - 原始标记文本】")
print(original_text)

# 执行 phoneme 替换
replaced_text = preprocess_phoneme_markers(original_text)

print("\n【替换后 - phoneme已替换】")
print(replaced_text)

print("\n" + "=" * 80)
print("🔍 分片后的 SSML 片段")
print("=" * 80)

# 模拟 tts_advanced.py 的分片逻辑
from app.tts_parser import parse_marked_text

segments = parse_marked_text(replaced_text)

for i, seg in enumerate(segments):
    if seg.segment_type == 'pause':
        print(f"\n片段 {i+1}: [停顿 {seg.rate}ms]")
    else:
        # 构建 SSML
        tc = TTSConfig(
            voice="zh-CN-YunjianNeural",
            rate=seg.rate,
            volume="+0%",
            pitch=seg.pitch,
            boundary="SentenceBoundary"
        )
        
        ssml = mkssml(tc, seg.text.encode('utf-8'))
        
        print(f"\n片段 {i+1}:")
        print(f"  文本: {seg.text}")
        print(f"  Rate: {seg.rate}, Pitch: {seg.pitch}")
        print(f"  SSML:")
        print(f"    {ssml}")

print("\n" + "=" * 80)
print("✅ 完成")
print("=" * 80)

# 生成音频文件
print("\n" + "=" * 80)
print("🎙️  生成音频文件供复核")
print("=" * 80)

async def generate_audio():
    line = ScriptLine(
        text=original_text,
        voice="zh-CN-YunjianNeural",
        type="narration",
        character="旁白",
        emotion="dramatic",
        rate="+0%",
        pitch="+0Hz"
    )
    
    output_path = "data/audio/test_ssml_verification.mp3"
    print(f"\n输出文件: {output_path}")
    print(f"原始文本: {original_text[:100]}...")
    
    try:
        duration = await synthesize_single_line(line, output_path)
        file_size = os.path.getsize(output_path)
        
        print(f"\n✅ 音频生成成功！")
        print(f"   时长: {duration:.2f} 秒")
        print(f"   大小: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print(f"   文件: {output_path}")
        print(f"\n🎧 请试听复核效果！")
        
    except Exception as e:
        print(f"\n❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(generate_audio())
