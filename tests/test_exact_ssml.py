"""测试完全按照 mkssml 格式构建的 SSML"""
import asyncio
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 导入补丁
from app import patch_edge_tts_v2

import edge_tts
from edge_tts.data_classes import TTSConfig
from edge_tts.communicate import mkssml, ssml_headers_plus_data, connect_id, date_to_string
from xml.sax.saxutils import escape

async def test_exact_ssml():
    """使用完全一致的 SSML 格式"""
    
    print("=" * 80)
    print("测试：使用与 mkssml 完全一致的 SSML 格式")
    print("=" * 80)
    
    # 准备参数
    text = "这是一个测试。"
    voice = "zh-CN-YunjianNeural"
    rate = "+0%"
    pitch = "+0Hz"
    volume = "+0%"
    
    # 创建 TTSConfig（和 edge-tts 内部一样）
    tc = TTSConfig(voice, rate, volume, pitch, "SentenceBoundary")
    
    # 模拟 edge-tts 的处理流程
    escaped_text = escape(text)
    
    # 调用原始 mkssml 生成 SSML
    ssml = mkssml(tc, escaped_text)
    
    print(f"\n原始文本: {text}")
    print(f"\n生成的 SSML:")
    print(ssml)
    print(f"\nSSML 长度: {len(ssml)} 字符")
    
    # 直接发送给 edge-tts
    print(f"\n{'='*80}")
    print("正在发送 SSML 到 Edge-TTS...")
    print(f"{'='*80}\n")
    
    try:
        communicate = edge_tts.Communicate(
            text=ssml,  # 直接传入完整的 SSML
            voice=voice,
            rate=rate,
            pitch=pitch,
            proxy=None
        )
        
        output_path = "data/audio/test_exact_ssml.mp3"
        await communicate.save(output_path)
        
        print(f"\n✅ 成功生成: {output_path}")
        print(f"文件大小: {os.path.getsize(output_path)} bytes")
        
    except Exception as e:
        print(f"\n❌ 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_exact_ssml())
