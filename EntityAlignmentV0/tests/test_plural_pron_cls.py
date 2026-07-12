#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
复数代词分类模型测试脚本 - 修复版
"""

import os
import sys
import json
import torch
import numpy as np
from pathlib import Path
from collections import Counter
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)
from transformers import AutoTokenizer
import pandas as pd

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入训练脚本
from train_pronoun_classifier_xlmr import (
    XLMRobertaForPronounClassification,
    insert_target_markers,
    predict_pronoun
)

# 尝试导入可视化
try:
    import matplotlib.pyplot as plt
    import seaborn as sns

    HAS_VIZ = True
except ImportError:
    HAS_VIZ = False
    print("⚠️ 可视化库未安装，跳过图表生成")


# ==================== 数据加载函数 ====================
def load_test_data(jsonl_path):
    """加载测试数据（兼容 label/labels 字段）"""
    texts, starts, ends, pronouns, labels = [], [], [], [], []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            texts.append(data['text'])
            starts.append(data['char_start'])
            ends.append(data['char_end'])
            pronouns.append(data['pronoun'])
            # 兼容 'label' 和 'labels'
            label = data.get('label', data.get('labels', 0))
            labels.append(label)
    return texts, starts, ends, pronouns, labels


# ==================== 模型加载 ====================
def load_model_safe(model_path: str, device: str = None):
    """安全加载模型"""
    model_path = str(Path(model_path).resolve())
    print(f"📁 模型路径: {model_path}")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型路径不存在: {model_path}")

    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device(device)

    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    print(f"✅ Tokenizer 加载成功 (词表: {len(tokenizer)})")

    model = XLMRobertaForPronounClassification.from_pretrained(model_path)
    model.to(device)
    model.eval()

    print(f"✅ 模型加载成功 (设备: {device})")
    return model, tokenizer, device


# ==================== 批量预测 ====================
def batch_predict(texts, starts, ends, model, tokenizer, device, batch_size=32):
    """批量预测"""
    results = []
    total = len(texts)

    print(f"\n🔄 开始批量预测 (共 {total} 条)...")

    for i in range(0, total, batch_size):
        batch_texts = texts[i:i + batch_size]
        batch_starts = starts[i:i + batch_size]
        batch_ends = ends[i:i + batch_size]

        for j, (text, start, end) in enumerate(zip(batch_texts, batch_starts, batch_ends)):
            try:
                result = predict_pronoun(
                    text=text,
                    char_start=start,
                    char_end=end,
                    model=model,
                    tokenizer=tokenizer,
                    device=device
                )
                results.append({
                    'text': text,
                    'char_start': start,
                    'char_end': end,
                    'pred_label': result['label'],
                    'pred_name': '复数' if result['label'] == 1 else '单数',
                    'confidence': result['confidence'],
                    'prob_plural': result['prob_plural']
                })
            except Exception as e:
                print(f"   ⚠️ 预测失败: {e}")
                results.append({
                    'text': text,
                    'char_start': start,
                    'char_end': end,
                    'pred_label': -1,
                    'pred_name': '失败',
                    'confidence': 0.0,
                    'prob_plural': 0.0
                })

        progress = min(i + batch_size, total)
        print(f"  进度: {progress}/{total} ({progress / total * 100:.1f}%)")

    print(f"✅ 预测完成")
    return results


# ==================== 评估指标 ====================
def compute_metrics(results, true_labels):
    """计算评估指标"""
    y_true = true_labels[:len(results)]
    y_pred = [r['pred_label'] for r in results if r['pred_label'] != -1]

    # 过滤失败样本
    valid_indices = [i for i, r in enumerate(results) if r['pred_label'] != -1]
    y_true_filtered = [y_true[i] for i in valid_indices]
    confidences = [r['confidence'] for r in results if r['pred_label'] != -1]

    if len(y_true_filtered) == 0:
        return None

    metrics = {
        'accuracy': accuracy_score(y_true_filtered, y_pred),
        'precision': precision_score(y_true_filtered, y_pred, average='binary', zero_division=0),
        'recall': recall_score(y_true_filtered, y_pred, average='binary', zero_division=0),
        'f1': f1_score(y_true_filtered, y_pred, average='binary', zero_division=0),
        'confusion_matrix': confusion_matrix(y_true_filtered, y_pred),
        'avg_confidence': np.mean(confidences) if confidences else 0,
        'min_confidence': np.min(confidences) if confidences else 0,
        'max_confidence': np.max(confidences) if confidences else 0,
        'total_samples': len(results),
        'valid_samples': len(y_true_filtered),
        'failed_samples': len(results) - len(y_true_filtered),
        'correct_count': sum(1 for i, r in enumerate(results)
                             if r['pred_label'] != -1 and r['pred_label'] == y_true[i])
    }

    return metrics


# ==================== 可视化 ====================
def plot_confusion_matrix(cm, labels=['单数', '复数'], save_path=None):
    """绘制混淆矩阵"""
    if not HAS_VIZ:
        return

    # 确保目录存在
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=labels, yticklabels=labels)
    plt.title('混淆矩阵 (Confusion Matrix)')
    plt.ylabel('真实标签')
    plt.xlabel('预测标签')
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"   💾 混淆矩阵已保存: {save_path}")
    plt.close()


def plot_confidence_distribution(results, save_path=None):
    """绘制置信度分布"""
    if not HAS_VIZ:
        return

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

    confidences = [r['confidence'] for r in results if r['pred_label'] != -1]
    if not confidences:
        return

    plt.figure(figsize=(10, 6))
    plt.hist(confidences, bins=20, alpha=0.7, edgecolor='black')
    plt.axvline(np.mean(confidences), color='red', linestyle='--',
                label=f'平均: {np.mean(confidences):.3f}')
    plt.title('置信度分布')
    plt.xlabel('置信度')
    plt.ylabel('样本数')
    plt.legend()
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"   💾 置信度分布已保存: {save_path}")
    plt.close()


# ==================== 打印报告 ====================
def print_report(metrics, results, true_labels):
    """打印评估报告"""
    print("\n" + "=" * 60)
    print("📊 评估报告")
    print("=" * 60)

    if metrics is None:
        print("❌ 没有有效的预测结果")
        return

    y_true = true_labels[:len(results)]
    y_pred = [r['pred_label'] for r in results if r['pred_label'] != -1]
    valid_indices = [i for i, r in enumerate(results) if r['pred_label'] != -1]
    y_true_filtered = [y_true[i] for i in valid_indices]

    print(f"\n📈 整体性能:")
    print(f"   - 总样本数:     {metrics['total_samples']}")
    print(f"   - 有效预测:     {metrics['valid_samples']}")
    print(f"   - 失败预测:     {metrics['failed_samples']}")
    print(f"   - 正确预测:     {metrics['correct_count']}")
    print(f"   - 准确率:       {metrics['accuracy']:.4f} ({metrics['accuracy'] * 100:.2f}%)")
    print(f"   - 精确率:       {metrics['precision']:.4f}")
    print(f"   - 召回率:       {metrics['recall']:.4f}")
    print(f"   - F1 分数:      {metrics['f1']:.4f}")

    print(f"\n📊 置信度:")
    print(f"   - 平均:  {metrics['avg_confidence']:.4f}")
    print(f"   - 最小:  {metrics['min_confidence']:.4f}")
    print(f"   - 最大:  {metrics['max_confidence']:.4f}")

    print(f"\n📋 分类报告:")
    print(classification_report(
        y_true_filtered,
        y_pred,
        target_names=['单数', '复数'],
        digits=4
    ))

    print(f"\n📋 混淆矩阵:")
    cm = metrics['confusion_matrix']
    print(f"                 预测")
    print(f"                单数  复数")
    print(f"  真实  单数    {cm[0][0]:5d}  {cm[0][1]:5d}")
    print(f"        复数    {cm[1][0]:5d}  {cm[1][1]:5d}")


# ==================== 保存结果 ====================
def save_results(results, true_labels, metrics, output_dir='./test_results'):
    """保存结果"""
    os.makedirs(output_dir, exist_ok=True)

    # 合并结果
    df_data = []
    for i, r in enumerate(results):
        df_data.append({
            'text': r['text'],
            'char_start': r['char_start'],
            'char_end': r['char_end'],
            'true_label': true_labels[i] if i < len(true_labels) else -1,
            'true_name': '复数' if i < len(true_labels) and true_labels[i] == 1 else '单数',
            'pred_label': r['pred_label'],
            'pred_name': r['pred_name'],
            'confidence': r['confidence'],
            'prob_plural': r['prob_plural'],
            'correct': r['pred_label'] == true_labels[i] if r['pred_label'] != -1 and i < len(true_labels) else False
        })

    df = pd.DataFrame(df_data)
    df.to_csv(f'{output_dir}/detailed_results.csv', index=False, encoding='utf-8-sig')
    print(f"💾 详细结果: {output_dir}/detailed_results.csv")

    if metrics:
        with open(f'{output_dir}/metrics_summary.json', 'w', encoding='utf-8') as f:
            json.dump({
                'accuracy': float(metrics['accuracy']),
                'precision': float(metrics['precision']),
                'recall': float(metrics['recall']),
                'f1': float(metrics['f1']),
                'confusion_matrix': metrics['confusion_matrix'].tolist(),
            }, f, indent=2, ensure_ascii=False)
        print(f"💾 指标摘要: {output_dir}/metrics_summary.json")


# ==================== 困难样本 ====================
def get_hard_cases():
    """获取困难测试样本"""
    return [
    ]


# ==================== 主函数 ====================
def run_test(model_path: str, test_data_path: str = None, output_dir: str = './test_results'):
    """运行完整测试"""
    print("=" * 60)
    print("🧪 复数代词分类模型测试")
    print("=" * 60)

    # 1. 加载模型
    print("\n1️⃣ 加载模型...")
    model, tokenizer, device = load_model_safe(model_path)

    # 2. 准备测试数据
    print("\n2️⃣ 准备测试数据...")
    all_texts, all_starts, all_ends, all_pronouns, all_labels = [], [], [], [], []

    # 2.1 加载测试文件
    if test_data_path and os.path.exists(test_data_path):
        try:
            texts, starts, ends, pronouns, labels = load_test_data(test_data_path)
            all_texts.extend(texts)
            all_starts.extend(starts)
            all_ends.extend(ends)
            all_pronouns.extend(pronouns)
            all_labels.extend(labels)
            print(f"   ✅ 从文件加载: {len(texts)} 条")
        except Exception as e:
            print(f"   ⚠️ 加载失败: {e}")

    # 2.2 添加困难样本
    hard_cases = get_hard_cases()
    for case in hard_cases:
        all_texts.append(case['text'])
        all_starts.append(case['start'])
        all_ends.append(case['end'])
        all_pronouns.append('')  # 无代词
        all_labels.append(case['label'])
    print(f"   ✅ 添加困难样本: {len(hard_cases)} 条")

    print(f"   📊 总计: {len(all_texts)} 条测试数据")

    # 标签分布
    label_counts = Counter(all_labels)
    print(f"\n📊 标签分布:")
    print(f"   - 单数 (0): {label_counts.get(0, 0)} 条")
    print(f"   - 复数 (1): {label_counts.get(1, 0)} 条")

    # 3. 批量预测
    results = batch_predict(all_texts, all_starts, all_ends, model, tokenizer, device)

    # 4. 计算指标
    print("\n3️⃣ 计算评估指标...")
    metrics = compute_metrics(results, all_labels)
    print_report(metrics, results, all_labels)

    # 5. 可视化
    if HAS_VIZ and metrics:
        print("\n4️⃣ 生成可视化图表...")

        # 混淆矩阵
        plot_confusion_matrix(
            metrics['confusion_matrix'],
            save_path=f'{output_dir}/confusion_matrix.png'
        )

        # 置信度分布
        plot_confidence_distribution(
            results,
            save_path=f'{output_dir}/confidence_distribution.png'
        )

    # 6. 保存结果
    print("\n5️⃣ 保存结果...")
    save_results(results, all_labels, metrics, output_dir)

    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)

    if metrics:
        print(f"\n📊 最终结果:")
        print(f"   - 准确率: {metrics['accuracy']:.2%}")
        print(f"   - F1: {metrics['f1']:.4f}")
        print(f"   - 正确: {metrics['correct_count']}/{metrics['valid_samples']}")

    return results, metrics


# ==================== 主入口 ====================
if __name__ == "__main__":
    # 配置路径
    MODEL_PATH = "../models_cache/plural_pron_cls1"
    TEST_DATA_PATH = "E:\Code\Python\PycharmProjects\EntityAlignmentV0\data\复数指代分类验证集 (1000条).jsonl"
    OUTPUT_DIR = "./test_results"

    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 运行测试
    results, metrics = run_test(
        model_path=MODEL_PATH,
        test_data_path=TEST_DATA_PATH,
        output_dir=OUTPUT_DIR
    )