"""
对比 edge-tts 在纯文本和自定义 SSML 模式下发送的协议
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 先导入补丁
import patch_edge_tts_v2

import edge_tts
from edge_tts.communicate import ssml_headers_plus_data, mkssml, connect_id, date_to_string
from edge_tts.data_classes import TTSConfig

def test_protocol():
    """模拟并打印两种模式的协议"""
    
    print("=" * 80)
    print("测试1：纯文本模式（edge-tts 自动构建 SSML）")
    print("=" * 80)
    
    # 模拟纯文本
    plain_text = "这是一个测试。"
    voice = "zh-CN-YunjianNeural"
    rate = "+0%"
    pitch = "+0Hz"
    volume = "+0%"
    
    # 创建 TTSConfig
    tts_config = TTSConfig(voice, rate, volume, pitch, "SentenceBoundary")
    
    # 模拟 edge-tts 的处理流程
    from xml.sax.saxutils import escape
    from edge_tts.communicate import remove_incompatible_characters
    
    escaped_text = escape(remove_incompatible_characters(plain_text))
    print(f"\n原始文本: {plain_text}")
    print(f"Escape 后: {escaped_text}")
    
    # 调用 mkssml
    ssml_result = mkssml(tts_config, escaped_text)
    print(f"\nMKSSML 生成的 SSML:\n{ssml_result}")
    
    # 生成完整的协议
    request_id = connect_id()
    timestamp = date_to_string()
    protocol = ssml_headers_plus_data(request_id, timestamp, ssml_result)
    print(f"\n完整协议:\n{protocol}")
    
    print("\n" + "=" * 80)
    print("测试2：自定义 SSML 模式")
    print("=" * 80)
    
    # 自定义 SSML
    custom_ssml = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>
<voice name='zh-CN-YunjianNeural'>
这是一个测试。
</voice>
</speak>"""
    
    print(f"\n自定义 SSML:\n{custom_ssml}")
    
    # 调用 mkssml（应该直接返回）
    ssml_result2 = mkssml(tts_config, custom_ssml)
    print(f"\nMKSSML 返回结果:\n{ssml_result2}")
    
    # 检查是否相同
    if ssml_result == ssml_result2:
        print("\n❌ 错误：两个 SSML 完全相同！说明补丁未生效")
    else:
        print("\n✅ 成功：两个 SSML 不同，补丁已生效")
    
    # 生成完整协议
    protocol2 = ssml_headers_plus_data(request_id, timestamp, ssml_result2)
    print(f"\n完整协议:\n{protocol2}")
    
    print("\n" + "=" * 80)
    print("对比分析")
    print("=" * 80)
    
    # 检查关键差异
    if '<prosody' in ssml_result and '<prosody' not in ssml_result2:
        print("✅ 自定义 SSML 模式没有额外的 <prosody> 标签")
    else:
        print("⚠️  注意：<prosody> 标签情况异常")
    
    if 'xml:lang=\'zh-CN\'' in ssml_result2:
        print("✅ 自定义 SSML 保留了原始的 xml:lang='zh-CN'")
    else:
        print("❌ 自定义 SSML 的 xml:lang 被修改了")

if __name__ == "__main__":
    test_protocol()
