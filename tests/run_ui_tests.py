"""
UI 布局重构测试运行器
在每次发布前运行此脚本进行验证
"""
import subprocess
import sys
import os

def run_tests():
    """运行所有 UI 测试"""
    print("=" * 80)
    print("🧪 TTS Studio - 完整测试套件")
    print("=" * 80)
    print()
    
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 运行所有测试
    test_files = [
        os.path.join(project_root, "tests", "test_ui_layout.py"),
        os.path.join(project_root, "tests", "test_e2e_routes.py"),
    ]
    
    all_passed = True
    
    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"⚠️  测试文件不存在: {test_file}")
            continue
        
        print(f"\n{'='*80}")
        print(f"📋 运行测试: {os.path.basename(test_file)}")
        print(f"{'='*80}\n")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
                capture_output=False,
                cwd=project_root
            )
            
            if result.returncode != 0:
                all_passed = False
                
        except Exception as e:
            print(f"❌ 测试执行失败: {e}")
            all_passed = False
    
    print()
    if all_passed:
        print("=" * 80)
        print("✅ 所有测试通过！可以安全发布")
        print("=" * 80)
    else:
        print("=" * 80)
        print("❌ 部分测试失败！请修复问题后再发布")
        print("=" * 80)
    
    return all_passed


def check_service_startup():
    """检查服务能否正常启动"""
    print()
    print("=" * 80)
    print("🚀 检查服务启动")
    print("=" * 80)
    print()
    
    # 添加项目根目录到路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    # 尝试导入并构建 UI
    try:
        from app.ui import build_ui
        demo = build_ui()
        print("✅ UI 构建成功")
        return True
    except Exception as e:
        print(f"❌ UI 构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print()
    
    # 1. 检查服务启动
    if not check_service_startup():
        print("\n❌ 服务启动检查失败，终止测试")
        sys.exit(1)
    
    print()
    
    # 2. 运行单元测试
    if not run_tests():
        sys.exit(1)
    
    print()
    print("=" * 80)
    print("🎉 发布前检查完成！")
    print("=" * 80)
    print()
    print("📝 发布检查清单:")
    print("  ✅ UI 构建成功")
    print("  ✅ 所有单元测试通过")
    print("  ⏸️  需要手动检查:")
    print("      - 访问 http://localhost:7860 确认界面正常")
    print("      - 测试多音字标注功能")
    print("      - 测试停顿插入功能")
    print("      - 测试对白编辑和应用")
    print("      - 测试工程保存和加载")
    print()


if __name__ == "__main__":
    main()
