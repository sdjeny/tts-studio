import gradio as gr
import logging
from pathlib import Path
from .ui import build_ui
from .config import DATA_DIR

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme=gr.themes.Soft(),
        allowed_paths=[str(DATA_DIR)],
        css="""
        .compact-table {
            max-height: 150px !important;
            overflow-y: auto !important;
        }
        .compact-table .table-wrap {
            max-height: 150px !important;
            overflow-y: auto !important;
        }
        .compact-table table {
            display: block !important;
        }
        /* 隐藏Dataframe的工具栏（复制、最大化按钮） */
        .compact-table .toolbar {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            min-height: 0 !important;
            max-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
        }
        .compact-table .toolbar * {
            display: none !important;
        }
        """
    )
