"""
基金分析技能 - 快速安装指南
"""

import os
import sys
import subprocess


def check_python_version():
    """检查Python版本"""
    print("检查Python版本...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ 需要Python 3.8或更高版本")
        return False
    print(f"✓ Python版本: {version.major}.{version.minor}.{version.micro}")
    return True


def install_dependencies():
    """安装依赖包"""
    print("\n安装依赖包...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install",
            "-r", "requirements.txt",
            "--quiet"
        ], check=True)
        print("✓ 依赖包安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖包安装失败: {e}")
        return False


def check_pysnowball_path():
    """检查pysnowball路径"""
    print("\n检查pysnowball路径...")
    pysnowball_path = "/Users/weijiahao03/play/pysnowball-master"

    if os.path.exists(pysnowball_path):
        print(f"✓ pysnowball路径存在: {pysnowball_path}")
        return True
    else:
        print(f"⚠️ pysnowball路径不存在: {pysnowball_path}")
        print("请确保pysnowball已下载到指定位置")
        print("或在data_fetcher.py中修改pysnowball路径")
        return False


def create_directories():
    """创建必要的目录"""
    print("\n创建必要的目录...")
    dirs_to_create = [
        "logs",
        "examples"
    ]

    for dir_name in dirs_to_create:
        dir_path = os.path.join(os.path.dirname(__file__), dir_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"✓ 创建目录: {dir_name}")
        else:
            print(f"✓ 目录已存在: {dir_name}")

    return True


def run_test():
    """运行测试"""
    print("\n运行快速测试...")
    try:
        # 导入测试
        from scripts.data_fetcher import DanjuanDataFetcher
        print("✓ 成功导入DataFetcher")

        from scripts.fund_analyzer import FundAnalyzer
        print("✓ 成功导入FundAnalyzer")

        print("\n✓ 所有模块导入成功,安装完成!")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("基金分析技能 - 安装向导")
    print("=" * 80 + "\n")

    # 检查Python版本
    if not check_python_version():
        return

    # 安装依赖
    if not install_dependencies():
        return

    # 检查pysnowball路径
    check_pysnowball_path()

    # 创建目录
    create_directories()

    # 运行测试
    if not run_test():
        return

    print("\n" + "=" * 80)
    print("安装完成!")
    print("=" * 80)
    print("\n使用方法:")
    print("  python scripts/fund_analyzer.py <基金代码>")
    print("\n示例:")
    print("  python scripts/fund_analyzer.py 008975")
    print("\n查看示例:")
    print("  python scripts/example.py 1")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
