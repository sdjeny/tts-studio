"""Patch edge-tts to support custom SSML"""
import edge_tts.communicate
from xml.sax.saxutils import escape as _original_escape

# Store original functions
_original_init = edge_tts.communicate.Communicate.__init__
_original_mkssml = edge_tts.communicate.mkssml

def patched_init(self, text, voice='en-US-EmmaMultilingualNeural', *, rate='+0%', volume='+0%', pitch='+0Hz', boundary='SentenceBoundary', connector=None, proxy=None, connect_timeout=10, receive_timeout=60):
    """Patched __init__ that supports custom SSML"""
    from edge_tts.data_classes import TTSConfig
    from edge_tts.constants import DEFAULT_VOICE
    from edge_tts.communicate import split_text_by_byte_length, remove_incompatible_characters
    from edge_tts.typing import CommunicateState
    import aiohttp
    
    # Validate TTS settings and store the TTSConfig object.
    self.tts_config = TTSConfig(voice, rate, volume, pitch, boundary)

    # Validate the text parameter.
    if not isinstance(text, str):
        raise TypeError("text must be str")

    # Check if text is custom SSML
    is_custom_ssml = text.strip().startswith('<speak')

    # Split the text into multiple strings and store them.
    if is_custom_ssml:
        # For custom SSML, don't escape - use as-is
        self.texts = [text.encode('utf-8')]
        self._is_custom_ssml = True
    else:
        # For normal text, escape and split
        self.texts = split_text_by_byte_length(
            _original_escape(remove_incompatible_characters(text)),
            4096,
        )
        self._is_custom_ssml = False

    # Validate the proxy parameter.
    if proxy is not None and not isinstance(proxy, str):
        raise TypeError("proxy must be str")
    self.proxy = proxy

    # Validate the timeout parameters.
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

    # Validate the connector parameter.
    if connector is not None and not isinstance(connector, aiohttp.BaseConnector):
        raise TypeError("connector must be aiohttp.BaseConnector")
    self.connector = connector

    # Store current state of TTS.
    self.state = {
        "partial_text": b"",
        "offset_compensation": 0,
        "last_duration_offset": 0,
        "stream_was_called": False,
        "chunk_audio_bytes": 0,
        "cumulative_audio_bytes": 0,
    }

def patched_mkssml(tc, escaped_text):
    """Patched mkssml that doesn't double-wrap custom SSML"""
    # If this is already a complete SSML document, return it as-is
    if isinstance(escaped_text, bytes):
        escaped_text_str = escaped_text.decode('utf-8')
    else:
        escaped_text_str = escaped_text
    
    if escaped_text_str.strip().startswith('<speak'):
        # Already complete SSML, return as-is (decode if bytes)
        if isinstance(escaped_text, bytes):
            return escaped_text
        return escaped_text_str
    
    # Normal text, build SSML as usual
    if isinstance(escaped_text, bytes):
        escaped_text = escaped_text.decode("utf-8")

    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        f"<voice name='{tc.voice}'>"
        f"<prosody pitch='{tc.pitch}' rate='{tc.rate}' volume='{tc.volume}'>"
        f"{escaped_text}"
        "</prosody>"
        "</voice>"
        "</speak>"
    )

# Apply patches
edge_tts.communicate.Communicate.__init__ = patched_init
edge_tts.communicate.mkssml = patched_mkssml

print("✅ edge-tts patched successfully!")
