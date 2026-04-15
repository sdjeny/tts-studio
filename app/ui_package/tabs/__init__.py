"""
UI Tab 页面模块

包含各个功能标签页的构建函数
"""

from .project_tab import build_project_tab
from .parse_tab import build_parse_tab
from .edit_tab import build_edit_tab
from .mix_tab import build_mix_tab

__all__ = ['build_project_tab', 'build_parse_tab', 'build_edit_tab', 'build_mix_tab']
