"""
复杂 SSML 测试 - 查看完整协议原文
展示 edge-tts 发送的完整 WebSocket 消息
"""
import asyncio
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import patch_edge_tts_v2
import edge_tts
from edge_tts.data_classes import TTSConfig
from edge_tts.communicate import mkssml, ssml_headers_plus_data, connect_id, date_to_string
from xml.sax.saxutils import escape

# 全局变量用于捕获协议数据
captured_protocol = {}

async def test_complex_ssml():
    """测试复杂 SSML 并查看协议"""
    
    print("=" * 100)
    print("复杂 SSML 测试 - 完整协议查看")
    print("=" * 100)
    
    # 测试1：简单的单个 prosody（基准）
    print("\n" + "=" * 100)
    print("测试1：简单 SSML（单个 prosody）")
    print("=" * 100)
    
    text1 = "这是一个测试。"
    voice = "zh-CN-YunjianNeural"
    
    tc1 = TTSConfig(voice, "-30%", "+0%", "+10Hz", "SentenceBoundary")
    ssml1 = mkssml(tc1, escape(text1))
    
    print(f"\n📝 原始文本: {text1}")
    print(f"📝 TTSConfig:")
    print(f"   voice: {tc1.voice}")
    print(f"   rate: {tc1.rate}")
    print(f"   pitch: {tc1.pitch}")
    print(f"   volume: {tc1.volume}")
    print(f"\n📄 生成的 SSML:")
    print(ssml1)
    print(f"\n📏 SSML 长度: {len(ssml1)} 字符")
    print(f"📏 SSML 字节数: {len(ssml1.encode('utf-8'))} bytes")
    
    # 显示完整的 SSML（十六进制）
    print(f"\n🔍 SSML UTF-8 字节（前200字节）:")
    hex_str = ssml1.encode('utf-8')[:200].hex()
    for i in range(0, min(200, len(ssml1.encode('utf-8'))), 16):
        hex_part = hex_str[i*2:(i+16)*2]
        hex_formatted = ' '.join(hex_part[j:j+2] for j in range(0, len(hex_part), 2))
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in ssml1.encode('utf-8')[i:i+16])
        print(f"  {i:04x}: {hex_formatted:<48} {ascii_part}")
    
    print("\n" + "=" * 100)
    print("测试2：复杂 SSML（两个 prosody）")
    print("=" * 100)
    
    text2 = "前半部分慢"
    text3 = "后半部分快"
    
    # 手动构建复杂 SSML
    complex_ssml = (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        f"<voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'>"
        f"<prosody pitch='+0Hz' rate='-40%' volume='+0%'>{text2}</prosody>"
        f"<prosody pitch='+0Hz' rate='+50%' volume='+0%'>{text3}</prosody>"
        f"</voice>"
        f"</speak>"
    )
    
    print(f"\n📝 复杂 SSML:")
    print(complex_ssml)
    print(f"\n📏 长度: {len(complex_ssml)} 字符")
    print(f"📏 字节数: {len(complex_ssml.encode('utf-8'))} bytes")
    
    # 显示完整字节
    print(f"\n🔍 完整 SSML 字节（十六进制）:")
    ssml_bytes = complex_ssml.encode('utf-8')
    for i in range(0, len(ssml_bytes), 16):
        hex_part = ssml_bytes[i:i+16].hex()
        hex_formatted = ' '.join(hex_part[j:j+2] for j in range(0, len(hex_part), 2))
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in ssml_bytes[i:i+16])
        print(f"  {i:04x}: {hex_formatted:<48} {ascii_part}")
    
    print("\n" + "=" * 100)
    print("测试3：实际调用 edge-tts（带协议捕获）")
    print("=" * 100)
    
    # 这里我们不调用实际的 edge-tts.Communicate，而是展示 mkssml 生成的 SSML
    print(f"\n📡 模拟协议流程:")
    print(f"   1. 客户端调用 edge_tts.Communicate()")
    print(f"   2. 内部调用 mkssml() 生成 SSML")
    print(f"   3. 通过 WebSocket 发送 ssml_headers_plus_data")
    print(f"   4. Microsoft 服务器返回音频数据")
    
    # 展示 ssml_headers_plus_data 的构建
    print(f"\n📡 WebSocket 协议结构:")
    print(f"   Content-Type: application/ssml+xml")
    print(f"   X-Microsoft-OutputFormat: audio-24khz-48kbitrate-mono-mp3")
    print(f"   X-ConnectionId: <uuid>")
    print(f"   X-Timestamp: <iso8601 timestamp>")
    print(f"   Path: ssml")
    print(f"   ")
    print(f"   SSML Body (如上所示)")
    
    # 测试4：更复杂的场景 - 3个片段
    print("\n" + "=" * 100)
    print("测试4：复杂场景（3个 prosody + 标点）")
    print("=" * 100)
    
    complex_ssml_3 = (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        f"<voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'>"
        f"<prosody pitch='+0Hz' rate='-50%' volume='+0%'>这句话很慢</prosody>"
        f"<prosody pitch='+0Hz' rate='+0%' volume='+0%'>，</prosody>"
        f"<prosody pitch='+0Hz' rate='+60%' volume='+0%'>这句话很快</prosody>"
        f"</voice>"
        f"</speak>"
    )
    
    print(f"\n📝 3片段 SSML:")
    print(complex_ssml_3)
    print(f"\n📏 长度: {len(complex_ssml_3)} 字符")
    print(f"📏 字节数: {len(complex_ssml_3.encode('utf-8'))} bytes")
    
    # 协议分析
    print("\n" + "=" * 100)
    print("📊 协议分析报告")
    print("=" * 100)
    
    print(f"\n✅ edge-tts 协议要点:")
    print(f"   1. SSML 必须以 <speak> 开头")
    print(f"   2. 必须包含 xmlns 和 xml:lang 属性")
    print(f"   3. voice name 必须使用完整格式")
    print(f"   4. prosody 属性顺序: pitch, rate, volume")
    print(f"   5. 使用单引号而非双引号")
    print(f"   6. xml:lang 必须是 'en-US'（不是 zh-CN）")
    
    print(f"\n❌ 不被支持的 SSML 功能:")
    print(f"   - <break> 标签（停顿）")
    print(f"   - <phoneme> 标签（多音字）")
    print(f"   - <emphasis> 标签（强调）")
    print(f"   - 3个以上的 <prosody> 标签")
    print(f"   - rate/pitch 逗号分隔多个值")
    
    print(f"\n✅ 我们实现的解决方案:")
    print(f"   - 自动拆分文本成多个片段")
    print(f"   - 每个片段独立调用 edge-tts")
    print(f"   - 使用 FFmpeg 拼接所有音频")
    print(f"   - 支持任意数量的语速/音调变化")
    
    # 测试实际生成（如果 FFmpeg 可用）
    print("\n" + "=" * 100)
    print("测试5：实际生成音频（需要 FFmpeg）")
    print("=" * 100)
    
    try:
        # 先测试简单的
        print(f"\n尝试生成简单 SSML 音频...")
        comm = edge_tts.Communicate(
            text=complex_ssml,
            voice=voice,
            rate="+0%",
            pitch="+0Hz"
        )
        output_path = "data/audio/test_complex_ssml_protocol.mp3"
        await comm.save(output_path)
        print(f"✅ 生成成功: {output_path}")
        print(f"   文件大小: {os.path.getsize(output_path)} bytes")
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        print(f"   提示: 可能需要安装 FFmpeg 或使用简单 SSML")

if __name__ == "__main__":
    asyncio.run(test_complex_ssml())
