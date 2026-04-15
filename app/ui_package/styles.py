"""
UI 样式定义

包含自定义 CSS 样式，用于覆盖 Gradio 默认样式
"""

# 确认对话框样式 - 防止 Gradio 加载状态覆盖
CONFIRM_DIALOG_CSS = """
/* 确认框容器 - 强制红色边框和背景 */
.confirm-box,
.confirm-box[class*="generating"],
.confirm-box[class*="loading"],
.confirm-box[style*="border-color: rgb(59, 130, 246)"],
.confirm-box[style*="border-color: rgb(96, 165, 250)"] {
    border: 2px solid #ff4d4f !important;
    border-radius: 8px !important;
    background: #fff2f0 !important;
    padding: 12px !important;
    box-shadow: none !important;
}

/* 覆盖 Gradio 的 processing 状态 */
.confirm-box .wrap,
.confirm-box .generating,
.confirm-box [class*="loading"],
.confirm-box [class*="processing"] {
    border-color: #ff4d4f !important;
    background: #fff2f0 !important;
    opacity: 1 !important;
}

/* 确认框内所有元素 */
.confirm-box * {
    border-color: #ff4d4f !important;
}

/* 警告文本 */
.confirm-text,
.confirm-box .confirm-text {
    color: #cf1322 !important;
    font-weight: bold !important;
    font-size: 14px !important;
    margin-bottom: 10px !important;
    opacity: 1 !important;
}

/* 强制移除任何遮罩层 */
.confirm-box::before,
.confirm-box::after {
    display: none !important;
    background: transparent !important;
}

/* 覆盖 Gradio 6.x 的 loading 动画 */
.confirm-box .loading-shimmer,
.confirm-box .generating [class*="shimmer"],
.confirm-box [class*="animate-pulse"] {
    animation: none !important;
    background: #fff2f0 !important;
    opacity: 1 !important;
}

/* 确保按钮区域正常显示 */
.confirm-box .gr-row {
    background: #fff2f0 !important;
    border-color: #ff4d4f !important;
}

/* 覆盖任何可能的蓝色边框 */
.confirm-box[style*="blue"],
.confirm-box[style*="rgb(59"],
.confirm-box[style*="rgb(96"] {
    border-color: #ff4d4f !important;
}
"""

# 紧凑表格样式
COMPACT_TABLE_CSS = """
.compact-table {
    font-size: 12px;
}
.compact-table th {
    padding: 4px 8px;
}
.compact-table td {
    padding: 4px 8px;
}
"""

# 合并所有样式
def get_custom_css() -> str:
    """获取所有自定义 CSS"""
    return CONFIRM_DIALOG_CSS + COMPACT_TABLE_CSS
