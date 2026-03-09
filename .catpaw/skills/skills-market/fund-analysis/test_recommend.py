#!/usr/bin/env python3
"""
测试推荐功能的简单脚本
验证基于持仓风格的推荐功能是否正常工作
"""

import sys
import os
import json

# 添加scripts目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from fund_recommender import FundRecommender
from logger import logger

def test_get_popular_funds():
    """测试获取热门基金"""
    print("\n" + "="*60)
    print("测试1: 获取热门基金列表")
    print("="*60)
    
    recommender = FundRecommender()
    
    # 测试获取热门基金
    popular_funds = recommender._get_popular_funds(limit=20)
    print(f"\n✓ 获取到 {len(popular_funds)} 只热门基金")
    if popular_funds:
        print(f"  样本: {popular_funds[:5]}")
    
    return len(popular_funds) > 0

def test_style_classification():
    """测试基金类型分类"""
    print("\n" + "="*60)
    print("测试2: 基金类型分类")
    print("="*60)
    
    recommender = FundRecommender()
    
    test_cases = [
        ("债券型基金", "bond"),
        ("指数型ETF", "index"),
        ("股票型基金", "stock"),
        ("混合型基金", "mixed"),
        ("平衡混合", "mixed"),
        ("固定收益债券", "bond"),
    ]
    
    passed = 0
    for fund_type, expected_style in test_cases:
        style = recommender._classify_fund_type(fund_type, "999999")
        status = "✓" if style == expected_style else "✗"
        print(f"  {status} '{fund_type}' -> {style} (expected: {expected_style})")
        if style == expected_style:
            passed += 1
    
    print(f"\n通过率: {passed}/{len(test_cases)}")
    return passed == len(test_cases)

def test_style_sample_library():
    """测试风格样本库"""
    print("\n" + "="*60)
    print("测试3: 风格样本库")
    print("="*60)
    
    recommender = FundRecommender()
    
    print(f"\n样本库包含的风格:")
    for style, funds in recommender.STYLE_SAMPLE_LIBRARY.items():
        print(f"  - {style}: {len(funds)} 只基金")
        print(f"    {', '.join(funds[:3])}...")
    
    return len(recommender.STYLE_SAMPLE_LIBRARY) > 0

def test_get_style_popular_funds():
    """测试获取特定风格的基金"""
    print("\n" + "="*60)
    print("测试4: 获取特定风格的基金")
    print("="*60)
    
    recommender = FundRecommender()
    
    styles = ['stock', 'mixed', 'bond', 'index']
    for style in styles:
        funds = recommender._get_style_popular_funds(style, 5)
        print(f"  ✓ {style}: {len(funds)} 只基金 -> {', '.join(funds[:3])}")
    
    return True

def test_default_popular_funds():
    """测试默认热门基金"""
    print("\n" + "="*60)
    print("测试5: 默认热门基金库")
    print("="*60)
    
    recommender = FundRecommender()
    
    # 测试获取默认基金（不排除任何基金）
    default_funds = recommender._get_default_popular_funds(set(), 10)
    print(f"\n✓ 获取到 {len(default_funds)} 只默认基金")
    print(f"  {default_funds}")
    
    # 测试排除指定基金
    exclude_set = {'110022', '007751'}
    filtered_funds = recommender._get_default_popular_funds(exclude_set, 10)
    print(f"\n✓ 排除 {exclude_set} 后获取到 {len(filtered_funds)} 只基金")
    
    # 验证排除效果
    has_excluded = any(code in filtered_funds for code in exclude_set)
    if not has_excluded:
        print("  ✓ 排除成功")
    else:
        print("  ✗ 排除失败")
        return False
    
    return True

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("基金推荐功能测试套件")
    print("="*60)
    
    tests = [
        ("获取热门基金", test_get_popular_funds),
        ("基金类型分类", test_style_classification),
        ("风格样本库", test_style_sample_library),
        ("特定风格基金", test_get_style_popular_funds),
        ("默认基金库", test_default_popular_funds),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ 测试异常: {e}")
            results.append((test_name, False))
    
    # 打印总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\n总体: {passed}/{total} 通过")
    
    if passed == total:
        print("\n✓ 所有测试通过！推荐功能运行正常。")
        return 0
    else:
        print(f"\n✗ {total - passed} 个测试失败")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
