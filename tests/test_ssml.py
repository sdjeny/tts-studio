"""测试 SSML 功能"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tts_engine import synthesize_single_line
from app.models import ScriptLine

async def test_ssml():
    """测试自定义 SSML"""
    
    # 测试1：纯文本模式（正常）
    print("=" * 60)
    print("测试1：纯文本模式")
    print("=" * 60)
    
    line1 = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="",
        text="这是一个普通的测试文本。",
        voice="zh-CN-YunjianNeural",
        rate="-5%",
        pitch="+0Hz"
    )
    
    await synthesize_single_line(line1, "data/audio/test_normal.mp3")
    print(f"✅ 已生成: data/audio/test_normal.mp3\n")
    
    # 测试2：自定义 SSML - 语气起伏
    print("=" * 60)
    print("测试2：自定义 SSML - 语气起伏")
    print("=" * 60)
    
    ssml_text = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>
    <voice name='zh-CN-YunjianNeural'>
        <prosody rate="-15%">这句话前半部分慢一点</prosody>
        <break time="300ms"/>
        <prosody rate="+25%" pitch="+15Hz">后半部分快且高亢</prosody>
    </voice>
</speak>"""
    
    line2 = ScriptLine(
        type="dialogue",
        character="测试",
        emotion="",
        text=ssml_text,
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    await synthesize_single_line(line2, "data/audio/test_prosody.mp3")
    print(f"✅ 已生成: data/audio/test_prosody.mp3\n")
    
    # 测试3：自定义 SSML - 多音字标注
    print("=" * 60)
    print("测试3：自定义 SSML - 多音字标注")
    print("=" * 60)
    
    ssml_text2 = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>
    <voice name='zh-CN-YunxiNeural'>
        这个<phoneme alphabet="sapi" ph="zhong4">重</phoneme>要的事情说三遍。
        <break time="500ms"/>
        他的体<phoneme alphabet="sapi" ph="zhong4">重</phoneme>很标准。
    </voice>
</speak>"""
    
    line3 = ScriptLine(
        type="dialogue",
        character="测试",
        emotion="",
        text=ssml_text2,
        voice="zh-CN-YunxiNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    await synthesize_single_line(line3, "data/audio/test_phoneme.mp3")
    print(f"✅ 已生成: data/audio/test_phoneme.mp3\n")
    
    # 测试4：自定义 SSML - 停顿和强调
    print("=" * 60)
    print("测试4：自定义 SSML - 停顿和强调")
    print("=" * 60)
    
    ssml_text3 = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>
    <voice name='zh-CN-XiaoxiaoNeural'>
        请注意<break time="800ms"/>
        <emphasis level="strong">这是非常重要的信息</emphasis>
        <break time="500ms"/>
        请认真听。
    </voice>
</speak>"""
    
    line4 = ScriptLine(
        type="dialogue",
        character="测试",
        emotion="",
        text=ssml_text3,
        voice="zh-CN-XiaoxiaoNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    await synthesize_single_line(line4, "data/audio/test_emphasis.mp3")
    print(f"✅ 已生成: data/audio/test_emphasis.mp3\n")
    
    print("=" * 60)
    print("所有测试完成！")
    print("=" * 60)
    print("\n生成的文件：")
    print("  1. data/audio/test_normal.mp3 - 普通文本")
    print("  2. data/audio/test_prosody.mp3 - 语气起伏")
    print("  3. data/audio/test_phoneme.mp3 - 多音字标注")
    print("  4. data/audio/test_emphasis.mp3 - 停顿和强调")

if __name__ == "__main__":
    asyncio.run(test_ssml())
