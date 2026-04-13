#!/usr/bin/env python
"""启动 Gradio 服务"""
from app.ui import build_ui
demo = build_ui()
demo.launch(server_name='0.0.0.0', server_port=7860, share=False)
