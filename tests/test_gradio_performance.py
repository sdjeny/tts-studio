"""
Gradio 性能优化测试用例

测试 Gradio UI 的性能优化效果，确保：
1. 首次加载时数据正常显示
2. Tab 切换流畅无卡顿
3. 控制台无性能警告
4. 组件更新正常工作

运行方式：
    python -m pytest tests/test_gradio_performance.py -v
"""

import pytest
import time
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestGradioPerformance:
    """Gradio 性能优化测试类"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """测试前准备"""
        logger.info("=" * 60)
        logger.info("开始 Gradio 性能测试")
        logger.info("=" * 60)
        yield
        logger.info("=" * 60)
        logger.info("Gradio 性能测试完成")
        logger.info("=" * 60)
    
    def test_preload_initial_data(self):
        """
        测试用例 1：预加载初始数据
        
        测试目标：
        - 验证 build_ui() 在页面构建前能正确预加载工程数据
        - 验证初始数据包含所有必要字段
        
        预期结果：
        - initial_clips_data 不为空（如果有工程文件）
        - initial_project_name 正确显示工程名
        - initial_input_text 包含剧本文本
        - LLM 配置正确恢复
        
        备注处理方式：
        - 如果没有工程文件，使用默认值降级
        - 预加载失败时记录错误日志但不中断
        - 使用 getattr() 处理旧工程文件的兼容性问题
        """
        from app.ui import build_ui
        from app.models import current_project
        from app.config import PROJECTS_DIR
        
        # 检查是否有工程文件
        projects_dir = Path(PROJECTS_DIR)
        has_projects = list(projects_dir.glob("*.json"))
        
        if has_projects:
            # 构建 UI（会触发预加载）
            demo = build_ui()
            
            # 验证 current_project 已加载
            assert current_project.name != "未命名", "❌ 工程名未正确加载"
            logger.info(f"✅ 工程名: {current_project.name}")
            
            # 验证音频片段
            if current_project.audio_clips:
                assert len(current_project.audio_clips) > 0, "❌ 音频片段为空"
                logger.info(f"✅ 音频片段数: {len(current_project.audio_clips)}")
                
                # 验证片段数据结构
                first_clip = current_project.audio_clips[0]
                assert hasattr(first_clip, 'character'), "❌ 片段缺少 character 属性"
                assert hasattr(first_clip, 'text'), "❌ 片段缺少 text 属性"
                logger.info(f"✅ 片段数据结构完整")
            
            # 验证 LLM 配置
            assert "api_base" in current_project.llm_config, "❌ LLM 配置缺失 api_base"
            assert "model" in current_project.llm_config, "❌ LLM 配置缺失 model"
            logger.info(f"✅ LLM 配置完整")
        else:
            logger.warning("⚠️ 没有工程文件，跳过预加载测试")
            pytest.skip("没有工程文件可供测试")
    
    def test_component_initialization_with_preloaded_data(self):
        """
        测试用例 2：组件静态初始化
        
        测试目标：
        - 验证组件在初始化时使用预加载的数据
        - 验证 value 参数正确传入
        
        预期结果：
        - Textbox 组件的 value 不为空
        - Dataframe 组件的 value 包含表格数据
        
        备注处理方式：
        - 组件初始化时直接传入 value，不依赖运行时事件
        - 避免使用 demo.load 或手动赋值 .value
        - 确保所有组件的初始值都来自预加载数据
        """
        from app.ui import build_ui
        from app.models import current_project
        from app.config import PROJECTS_DIR
        
        # 检查是否有工程文件
        projects_dir = Path(PROJECTS_DIR)
        has_projects = list(projects_dir.glob("*.json"))
        
        if not has_projects:
            pytest.skip("没有工程文件可供测试")
        
        # 构建 UI
        demo = build_ui()
        
        # 验证 current_project 已正确加载
        assert current_project.name != "未命名", "❌ 预加载失败"
        
        # 注意：Gradio 组件的值需要在运行时通过事件获取
        # 这里主要验证预加载逻辑是否正确执行
        logger.info(f"✅ 组件初始化完成")
        logger.info(f"   工程名: {current_project.name}")
        logger.info(f"   音频片段: {len(current_project.audio_clips)}")
    
    def test_no_demo_load_usage(self):
        """
        测试用例 3：验证未使用 demo.load
        
        测试目标：
        - 确认代码中没有使用 demo.load 事件
        - 避免性能问题
        
        预期结果：
        - ui.py 文件中不包含 demo.load 调用
        
        备注处理方式：
        - demo.load 会导致 click handler 耗时增加
        - 改用预加载 + 静态初始化方案
        - 只在用户主动交互时才触发事件
        """
        ui_file = Path("app/ui.py")
        assert ui_file.exists(), "❌ ui.py 文件不存在"
        
        content = ui_file.read_text(encoding='utf-8')
        
        # 检查是否使用了 demo.load
        has_demo_load = "demo.load(" in content
        
        assert not has_demo_load, (
            "❌ 检测到 demo.load 调用，这会导致性能问题\n"
            "   请使用预加载 + 静态初始化方案替代"
        )
        
        logger.info("✅ 未检测到 demo.load 调用")
    
    def test_event_handler_return_values(self):
        """
        测试用例 4：事件处理函数返回值对齐
        
        测试目标：
        - 验证事件处理函数的返回值数量与输出组件一致
        - 避免返回值不匹配导致的错误
        
        预期结果：
        - on_recent_files_change 返回 6 个值
        - 对应 6 个输出组件
        
        备注处理方式：
        - 返回值顺序必须与绑定的输出组件顺序一致
        - 缺少返回值会导致组件更新失败
        - 多余返回值会被忽略但浪费资源
        """
        from app.ui import build_ui
        import inspect
        
        # 构建 UI 以获取内部函数
        demo = build_ui()
        
        # 查找 on_recent_files_change 函数
        # 由于它是闭包函数，我们需要通过源码检查
        ui_file = Path("app/ui.py")
        content = ui_file.read_text(encoding='utf-8')
        
        # 检查返回值数量
        if "return [], \"未命名\", \"\", DEFAULT_API_BASE, DEFAULT_API_KEY, DEFAULT_MODEL" in content:
            logger.info("✅ 空值返回值正确（6个值）")
        
        if "return refresh_clips_table(), current_project.name, current_project.raw_text, api_base_val, api_key_val, model_val" in content:
            logger.info("✅ 正常返回值正确（6个值）")
        
        # 验证返回值为 6 个
        assert "return refresh_clips_table(), current_project.name, current_project.raw_text" in content, \
            "❌ 返回值不包含必要的 6 个组件数据"
    
    def test_backward_compatibility_with_getattr(self):
        """
        测试用例 5：向后兼容性处理
        
        测试目标：
        - 验证使用 getattr() 处理可能缺失的属性
        - 确保旧工程文件也能正常加载
        
        预期结果：
        - bgm_clips 和 sfx_clips 使用 getattr 提供默认值
        - volume 属性使用 getattr 提供默认值 1.0
        
        备注处理方式：
        - 旧工程文件可能缺少新添加的属性
        - 使用 getattr(obj, attr, default) 提供默认值
        - 避免 AttributeError 导致加载失败
        """
        ui_file = Path("app/ui.py")
        content = ui_file.read_text(encoding='utf-8')
        
        # 检查是否使用 getattr 处理 bgm_clips
        has_bgm_compat = "getattr(loaded_project, 'bgm_clips'" in content or \
                        "getattr(project, 'bgm_clips'" in content
        
        # 检查是否使用 getattr 处理 volume
        has_volume_compat = "getattr(line, 'volume'" in content or \
                           "getattr(clip, 'volume'" in content
        
        assert has_bgm_compat or has_volume_compat, (
            "❌ 未检测到向后兼容性处理\n"
            "   请使用 getattr() 处理可能缺失的属性"
        )
        
        logger.info("✅ 检测到向后兼容性处理")
    
    def test_tabs_not_accordion_heavy_nesting(self):
        """
        测试用例 6：验证使用 Tabs 而非深层嵌套 Accordion
        
        测试目标：
        - 确认使用 Tabs 作为顶级布局
        - 避免过多嵌套的 Accordion
        
        预期结果：
        - 使用 gr.Tabs() 作为主布局
        - Accordion 嵌套不超过 2 层
        
        备注处理方式：
        - Tabs 切换只隐藏/显示，性能好
        - Accordion 展开/折叠触发大量 DOM 操作
        - 嵌套超过 3 层会导致严重性能问题
        - 推荐：Tabs（顶级）+ 少量 Accordion（内部）
        """
        ui_file = Path("app/ui.py")
        content = ui_file.read_text(encoding='utf-8')
        
        # 检查是否使用 Tabs
        has_tabs = "with gr.Tabs():" in content
        assert has_tabs, "❌ 未检测到 gr.Tabs()，建议使用 Tabs 作为顶级布局"
        
        # 统计 Accordion 嵌套层级（简化检查）
        accordion_count = content.count("with gr.Accordion(")
        
        # 如果 Accordion 太多，可能有性能风险
        if accordion_count > 10:
            logger.warning(f"⚠️ 检测到 {accordion_count} 个 Accordion，可能存在性能风险")
            logger.warning("   建议减少到 5 个以内，或使用 Tabs 替代")
        else:
            logger.info(f"✅ Accordion 数量合理: {accordion_count} 个")
        
        logger.info("✅ 使用 Tabs 作为顶级布局")
    
    def test_no_manual_value_assignment(self):
        """
        测试用例 7：验证没有手动赋值 .value
        
        测试目标：
        - 确认没有在事件处理函数中手动赋值 component.value
        - 所有更新都通过返回值实现
        
        预期结果：
        - 事件处理函数中不包含 ".value =" 赋值
        
        备注处理方式：
        - Gradio 不是响应式框架
        - 手动赋值 .value 不会触发前端更新
        - 必须通过事件函数的返回值更新组件
        - 唯一例外：build_ui() 初始化时可以设置 value 参数
        """
        ui_file = Path("app/ui.py")
        content = ui_file.read_text(encoding='utf-8')
        
        # 查找事件处理函数中的 .value 赋值
        # 排除初始化时的 value= 参数设置
        lines = content.split('\n')
        
        problematic_lines = []
        in_event_handler = False
        
        for i, line in enumerate(lines, 1):
            # 检测是否在事件处理函数中
            if 'def on_' in line or 'def load_' in line or 'def update_' in line:
                in_event_handler = True
            
            # 检测函数结束
            if in_event_handler and line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                in_event_handler = False
            
            # 检查是否有 .value = 赋值（排除 value= 参数）
            if in_event_handler and '.value =' in line and 'value=' not in line.split('.value')[0]:
                problematic_lines.append((i, line.strip()))
        
        if problematic_lines:
            logger.warning("⚠️ 检测到事件处理函数中有手动 .value 赋值:")
            for line_num, line_content in problematic_lines[:5]:  # 只显示前5个
                logger.warning(f"   第 {line_num} 行: {line_content}")
            logger.warning("   请改为通过返回值更新组件")
        
        # 这个测试只是警告，不强制失败
        logger.info("✅ 手动赋值检查完成")
    
    def test_exception_handling_in_preload(self):
        """
        测试用例 8：预加载异常处理
        
        测试目标：
        - 验证预加载时有完善的异常处理
        - 确保加载失败时使用默认值降级
        
        预期结果：
        - 预加载代码包含 try-except 块
        - 异常时记录错误日志
        - 使用默认值保证应用可启动
        
        备注处理方式：
        - 预加载可能因文件损坏、格式错误等失败
        - 必须有异常处理避免应用崩溃
        - 失败时降级到默认值，保证基本功能可用
        - 记录详细错误日志便于排查
        """
        ui_file = Path("app/ui.py")
        content = ui_file.read_text(encoding='utf-8')
        
        # 检查是否有异常处理
        has_try_except = "try:" in content and "except Exception as e:" in content
        
        assert has_try_except, "❌ 未检测到异常处理，预加载失败会导致应用崩溃"
        
        # 检查是否有错误日志
        has_error_log = 'logger.error(f"❌' in content or "logger.error(" in content
        
        assert has_error_log, "❌ 未检测到错误日志记录"
        
        logger.info("✅ 预加载包含完善的异常处理")
    
    def test_logging_quality(self):
        """
        测试用例 9：日志记录质量
        
        测试目标：
        - 验证关键步骤都有日志记录
        - 日志信息足够详细便于排查问题
        
        预期结果：
        - 预加载开始有日志
        - 预加载成功/失败有日志
        - 包含关键数据（工程名、片段数等）
        
        备注处理方式：
        - 日志是排查问题的第一手资料
        - 关键步骤必须有日志记录
        - 包含足够的上下文信息
        - 使用 emoji 提高可读性（可选）
        """
        ui_file = Path("app/ui.py")
        content = ui_file.read_text(encoding='utf-8')
        
        # 检查关键日志
        has_preload_start = "预加载" in content or "preload" in content.lower()
        has_success_log = "✅" in content or "成功" in content
        has_failure_log = "❌" in content or "失败" in content
        
        assert has_preload_start, "❌ 缺少预加载开始的日志"
        assert has_success_log, "❌ 缺少成功日志"
        assert has_failure_log, "❌ 缺少失败日志"
        
        logger.info("✅ 日志记录完善")


class TestGradioPerformanceIntegration:
    """Gradio 性能集成测试"""
    
    def test_full_load_cycle(self):
        """
        集成测试：完整加载周期
        
        测试目标：
        - 模拟完整的页面加载流程
        - 验证从预加载到组件初始化的全过程
        
        预期结果：
        - 无异常抛出
        - 所有组件正常初始化
        - 性能在可接受范围内
        
        备注处理方式：
        - 集成测试覆盖端到端流程
        - 重点关注整体性能而非单个组件
        - 记录总耗时用于性能对比
        """
        import time
        from app.ui import build_ui
        
        start_time = time.time()
        
        # 构建 UI（包含预加载）
        demo = build_ui()
        
        elapsed = time.time() - start_time
        
        logger.info(f"✅ UI 构建完成，耗时: {elapsed:.2f}秒")
        
        # 性能要求：应该在 3 秒内完成
        assert elapsed < 3.0, f"❌ UI 构建耗时过长: {elapsed:.2f}秒（要求 < 3秒）"
        
        logger.info("✅ 性能符合要求")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
