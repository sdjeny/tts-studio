"""
TTS Studio UI 模块

提供 Gradio 界面的构建和组件封装
"""

# 导出组件和样式（已模块化）
from .components import create_confirm_dialog, show_confirm_dialog, hide_confirm_dialog
from .styles import get_custom_css

__all__ = ['create_confirm_dialog', 'show_confirm_dialog', 'hide_confirm_dialog', 'get_custom_css']
