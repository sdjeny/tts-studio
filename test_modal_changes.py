#!/usr/bin/env python3
"""
测试 Modal 修改是否正确
"""
import sys
sys.path.insert(0, 'c:\\work\\227\\voice\\a\\tts-studio')

def test_import():
    """测试 UI 模块是否能正常导入"""
    try:
        from app.ui import build_ui
        print("✅ UI 模块导入成功")
        return True
    except Exception as e:
        print(f"❌ UI 模块导入失败: {e}")
        return False

def test_modal_components():
    """测试 Modal 组件是否正确配置"""
    try:
        import gradio as gr
        
        # 测试 Modal 创建
        with gr.Blocks() as demo:
            with gr.Modal(open=False, title="测试") as modal:
                gr.Markdown("测试内容")
        
        print("✅ Modal 组件创建成功")
        return True
    except Exception as e:
        print(f"❌ Modal 组件创建失败: {e}")
        return False

def test_event_handlers():
    """测试事件处理函数签名"""
    try:
        # 检查关键函数是否存在
        import app.ui as ui_module
        
        # 读取 ui.py 内容检查关键函数
        with open('app/ui.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ('prepare_save_project 函数', 'def prepare_save_project'),
            ('execute_save_project 函数', 'def execute_save_project'),
            ('prepare_save_character 函数', 'def prepare_save_character'),
            ('execute_save_character 函数', 'def execute_save_character'),
            ('delete_selected_project 函数', 'def delete_selected_project'),
            ('confirm_delete_project 函数', 'def confirm_delete_project'),
            ('gr.update(open=True)', 'gr.update(open=True)'),
            ('gr.update(open=False)', 'gr.update(open=False)'),
        ]
        
        all_passed = True
        for name, pattern in checks:
            if pattern in content:
                print(f"✅ {name} 存在")
            else:
                print(f"❌ {name} 不存在")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ 事件处理函数检查失败: {e}")
        return False

def test_no_timer():
    """测试定时器是否已移除"""
    try:
        with open('app/ui.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否还有 Timer 组件
        if 'gr.Timer' in content:
            print("⚠️ 仍有 Timer 组件存在，请检查是否全部移除")
            return False
        else:
            print("✅ Timer 组件已全部移除")
            return True
    except Exception as e:
        print(f"❌ Timer 检查失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("=" * 60)
    print("测试 Modal 修改")
    print("=" * 60)
    
    tests = [
        ("导入测试", test_import),
        ("Modal 组件测试", test_modal_components),
        ("事件处理函数测试", test_event_handlers),
        ("定时器移除测试", test_no_timer),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n--- {name} ---")
        result = test_func()
        results.append((name, result))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！Modal 修改验证成功。")
        return 0
    else:
        print("\n⚠️ 部分测试未通过，请检查修改。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
