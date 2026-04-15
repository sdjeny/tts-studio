"""
可复用 UI 组件

提供确认对话框等通用组件的封装
"""

import gradio as gr


def create_confirm_dialog(warning_text: str, confirm_text: str = "✅ 确认", cancel_text: str = "❌ 取消"):
    """
    创建带红色边框的确认对话框组件（按钮在框内）
    
    Args:
        warning_text: 警告信息
        confirm_text: 确认按钮文字
        cancel_text: 取消按钮文字
        
    Returns:
        tuple: (confirm_row, warning_md, confirm_btn, cancel_btn)
    """
    # 确认对话框（红色边框容器）
    with gr.Row(visible=False) as confirm_row:
        with gr.Column(elem_classes="confirm-box"):
            # 警告文本
            warning_md = gr.Markdown(
                f"<div class='confirm-text'>{warning_text}</div>"
            )
            # 按钮区域（在框内）
            with gr.Row():
                confirm_btn = gr.Button(confirm_text, variant="stop", size="sm")
                cancel_btn = gr.Button(cancel_text, size="sm")
    
    return confirm_row, warning_md, confirm_btn, cancel_btn


def show_confirm_dialog(confirm_row, warning_md, message: str):
    """
    显示确认对话框并更新警告信息
    
    Args:
        confirm_row: 确认行组件
        warning_md: 警告文本组件
        message: 要显示的警告消息
        
    Returns:
        tuple: (confirm_row_update, warning_md_update)
    """
    return (
        gr.update(visible=True),
        gr.update(value=f"<div class='confirm-text'>{message}</div>")
    )


def hide_confirm_dialog(confirm_row, warning_md):
    """
    隐藏确认对话框并清空警告信息
    
    Args:
        confirm_row: 确认行组件
        warning_md: 警告文本组件
        
    Returns:
        tuple: (confirm_row_update, warning_md_update)
    """
    return (
        gr.update(visible=False),
        gr.update(value="")
    )
