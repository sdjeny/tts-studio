"""对比 SSML 格式"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from edge_tts.data_classes import TTSConfig
from edge_tts.communicate import mkssml
from xml.sax.saxutils import escape

# 模拟 edge-tts 的处理
text = "这是一个测试。"
voice = "zh-CN-YunjianNeural"
rate = "+0%"
pitch = "+0Hz"
volume = "+0%"

# 创建 TTSConfig
tc = TTSConfig(voice, rate, volume, pitch, "SentenceBoundary")

# 模拟 edge-tts 的处理流程
escaped_text = escape(text)
print(f"原始文本: {text}")
print(f"Escape 后: {escaped_text}")

# 调用原始 mkssml
ssml_original = mkssml(tc, escaped_text)
print(f"\n原始 mkssml 生成的 SSML:")
print(ssml_original)
print(f"\nSSML 长度: {len(ssml_original)}")

# 对比我们之前构建的 SSML
ssml_ours = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>
    <voice name='{voice}'>
        <prosody rate="{rate}" pitch="{pitch}">{text}</prosody>
    </voice>
</speak>"""

print(f"\n我们构建的 SSML:")
print(ssml_ours)
print(f"\nSSML 长度: {len(ssml_ours)}")

print("\n" + "="*80)
print("差异分析:")
print("="*80)

if ssml_original == ssml_ours:
    print("✅ 完全相同")
else:
    print("❌ 不同，差异如下:")
    
    # 检查 xml:lang
    if "xml:lang='en-US'" in ssml_original:
        print("  - 原始使用 xml:lang='en-US'")
    if "xml:lang='zh-CN'" in ssml_ours:
        print("  - 我们使用 xml:lang='zh-CN'")
    
    # 检查是否有换行
    if '\n' not in ssml_original:
        print("  - 原始 SSML 没有换行（单行）")
    if '\n' in ssml_ours:
        print("  - 我们的 SSML 有换行和缩进")
    
    # 检查 voice 名称
    if 'Microsoft Server Speech' in ssml_original:
        print("  - 原始使用完整的 voice 名称")
    else:
        print(f"  - 原始 voice 名称: {voice}")
    
    # 检查 prosody 属性顺序
    if "pitch='" in ssml_original and "rate='" in ssml_original:
        print("  - 原始 prosody 属性顺序: pitch, rate, volume")
    if 'rate="' in ssml_ours and 'pitch="' in ssml_ours:
        print("  - 我们的 prosody 属性顺序: rate, pitch")
        print("  - 我们使用双引号，原始使用单引号")
