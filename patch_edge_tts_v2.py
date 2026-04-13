"""
强制让 edge-tts 支持自定义 SSML
通过直接替换 Communicate 类的关键方法
"""
import edge_tts.communicate
from edge_tts.data_classes import TTSConfig
from edge_tts.communicate import split_text_by_byte_length, remove_incompatible_characters
from xml.sax.saxutils import escape as _original_escape
import aiohttp

# 保存原始方法
_original_communicate_init = edge_tts.communicate.Communicate.__init__
_original_mkssml = edge_tts.communicate.mkssml

def patched_communicate_init(self, text, voice='en-US-EmmaMultilingualNeural', *, 
                              rate='+0%', volume='+0%', pitch='+0Hz', 
                              boundary='SentenceBoundary', connector=None, 
                              proxy=None, connect_timeout=10, receive_timeout=60):
    """
    修补后的 __init__，支持检测并保留自定义 SSML
    """
    # Validate TTS settings
    self.tts_config = TTSConfig(voice, rate, volume, pitch, boundary)

    # Validate the text parameter
    if not isinstance(text, str):
        raise TypeError("text must be str")

    # 检测是否是自定义 SSML
    is_custom_ssml = text.strip().startswith('<speak')
    
    if is_custom_ssml:
        # 对于自定义 SSML，不进行 escape，保持为字符串
        # 注意：必须是完整的 SSML 文档
        print(f"[DEBUG] 检测到自定义 SSML，跳过 escape")
        self.texts = [text]  # 保持为 str，不是 bytes!
        self._is_custom_ssml = True
    else:
        # 普通文本，正常处理
        escaped_text = _original_escape(remove_incompatible_characters(text))
        self.texts = split_text_by_byte_length(escaped_text, 4096)
        self._is_custom_ssml = False

    # 其余初始化代码保持不变
    if proxy is not None and not isinstance(proxy, str):
        raise TypeError("proxy must be str")
    self.proxy = proxy

    if not isinstance(connect_timeout, int):
        raise TypeError("connect_timeout must be int")
    if not isinstance(receive_timeout, int):
        raise TypeError("receive_timeout must be int")
    self.session_timeout = aiohttp.ClientTimeout(
        total=None,
        connect=None,
        sock_connect=connect_timeout,
        sock_read=receive_timeout,
    )

    if connector is not None and not isinstance(connector, aiohttp.BaseConnector):
        raise TypeError("connector must be aiohttp.BaseConnector")
    self.connector = connector

    self.state = {
        "partial_text": b"",
        "offset_compensation": 0,
        "last_duration_offset": 0,
        "stream_was_called": False,
        "chunk_audio_bytes": 0,
        "cumulative_audio_bytes": 0,
    }

def patched_mkssml(tc, escaped_text):
    """
    修补后的 mkssml，如果已经是完整 SSML 则直接返回
    """
    # 检查是否已经是完整 SSML（bytes 或 str）
    print(f"\n[DEBUG] mkssml called with type: {type(escaped_text)}")
    
    if isinstance(escaped_text, bytes):
        text_str = escaped_text.decode('utf-8')
        print(f"[DEBUG] Decoded bytes to str, length: {len(text_str)}")
    else:
        text_str = escaped_text
        print(f"[DEBUG] Already str, length: {len(text_str)}")
    
    print(f"[DEBUG] First 100 chars: {text_str[:100]}")
    
    if text_str.strip().startswith('<speak'):
        # 已经是完整 SSML，直接返回（保持原始类型）
        print(f"[DEBUG] Detected custom SSML, returning as-is")
        print(f"[SSML] {text_str}\n")
        return escaped_text
    
    # 普通文本，使用原始逻辑构建 SSML
    if isinstance(escaped_text, bytes):
        escaped_text = escaped_text.decode("utf-8")

    ssml = (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        f"<voice name='{tc.voice}'>"
        f"<prosody pitch='{tc.pitch}' rate='{tc.rate}' volume='{tc.volume}'>"
        f"{escaped_text}"
        "</prosody>"
        "</voice>"
        "</speak>"
    )
    
    print(f"[SSML] {ssml}\n")
    return ssml

# 应用补丁
edge_tts.communicate.Communicate.__init__ = patched_communicate_init
edge_tts.communicate.mkssml = patched_mkssml

print("OK: edge-tts patched successfully")
