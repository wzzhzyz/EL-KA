"""
共指解析测试脚本 - 输出含位置信息的共指链
"""

import json
import os
import sys
from typing import List, Dict
import numpy as np

# 导入训练脚本中的 CoreferenceResolver
from train_paraphase_coref import CoreferenceResolver


def load_test_data(json_file: str) -> List[Dict]:
    """加载测试数据"""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = [data]
    return data


def run_coreference_resolution(
    model_path: str = './finetuned_paraphase',
    test_file: str = './data/coref_test.json',
    threshold: float = 0.65,
    output_file: str = './coref_results.json'
):
    """运行共指解析，输出所有结果"""

    print("=" * 70)
    print("🔗 共指解析 - 批量处理")
    print("=" * 70)

    # 加载测试数据
    test_data = load_test_data(test_file)
    print(f"\n📁 加载测试数据: {len(test_data)} 条样本")

    # 初始化解析器
    print(f"\n🚀 加载模型: {model_path}")
    resolver = CoreferenceResolver(model_path=model_path, threshold=threshold)
    print(f"   阈值: {threshold}")

    # 存储所有结果
    all_results = []

    print(f"\n📊 开始处理...")
    print("-" * 70)

    for idx, item in enumerate(test_data):
        doc = item['doc']
        doc_id = item.get('doc_id', f'test_{idx+1:03d}')
        mentions = item['mentions']

        print(f"\n[{idx+1}/{len(test_data)}] 处理: {doc_id}")
        print(f"   Mentions: {len(mentions)}")

        try:
            # 预测
            result = resolver.predict(doc, mentions)

            # ===== 构建含位置信息的共指簇 =====
            clusters_with_position = []
            clusters_text = []

            for cluster in result['clusters']:
                # 每个簇包含完整的位置信息
                cluster_with_pos = []
                cluster_texts = []
                for m in cluster:
                    cluster_with_pos.append({
                        "text": doc[m['char_start']:m['char_end']],
                        "char_start": m['char_start'],
                        "char_end": m['char_end']
                    })
                    cluster_texts.append(doc[m['char_start']:m['char_end']])
                clusters_with_position.append(cluster_with_pos)
                clusters_text.append(cluster_texts)

            # 提取复数代词映射（含位置信息）
            plural_results = []
            for p in result.get('plural_results', []):
                plural_results.append({
                    "pronoun": p['pronoun'],
                    "referents": [
                        {
                            "text": ref,
                            # 注意：这里需要从原始数据中查找位置
                            # 由于 referents 只返回了文本，我们需要在 mentions 中查找
                            "char_start": None,
                            "char_end": None
                        }
                        for ref in p['referents']
                    ]
                })

            # 构建输出
            output_item = {
                "doc_id": doc_id,
                "doc": doc,
                "mentions": mentions,  # 原始mentions列表（含位置）
                "clusters": clusters_with_position,  # 共指簇（含位置信息）
                "clusters_text": clusters_text,  # 共指簇（纯文本，便于阅读）
                "plural_pronouns": plural_results,
                "pairwise_distances": result.get('pairwise_distances', [])[:10],
                "threshold_used": threshold
            }

            all_results.append(output_item)

            # 打印简要结果
            print(f"   ✅ 共指簇数: {len(clusters_with_position)}")
            for i, cluster in enumerate(clusters_with_position):
                if len(cluster) > 1:
                    texts = [m['text'] for m in cluster]
                    positions = [(m['char_start'], m['char_end']) for m in cluster]
                    print(f"     簇 {i+1}: {texts}")
                    print(f"         位置: {positions}")
                else:
                    print(f"     簇 {i+1}: [{cluster[0]['text']}] (孤立)")
                    print(f"         位置: ({cluster[0]['char_start']}, {cluster[0]['char_end']})")

        except Exception as e:
            print(f"   ❌ 错误: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({
                "doc_id": doc_id,
                "doc": doc,
                "error": str(e)
            })
            continue

    # 保存结果
    print("\n" + "=" * 70)
    print(f"💾 保存结果到: {output_file}")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # 打印统计
    total_clusters = sum(len(r.get('clusters', [])) for r in all_results if 'clusters' in r)
    total_mentions = sum(len(r.get('mentions', [])) for r in all_results if 'mentions' in r)

    print(f"\n📊 统计:")
    print(f"   处理样本: {len(all_results)}")
    print(f"   总 Mentions: {total_mentions}")
    print(f"   总共指簇: {total_clusters}")
    print(f"   平均每样本簇数: {total_clusters / len(all_results):.2f}")

    print("\n✅ 完成!")

    return all_results


def print_summary(results_file: str = './coref_results.json'):
    """打印结果摘要"""

    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)

    print("\n" + "=" * 70)
    print("📋 结果摘要 (含位置信息)")
    print("=" * 70)

    for item in results[:5]:  # 只打印前5条，避免太长
        doc_id = item.get('doc_id', 'unknown')
        clusters = item.get('clusters', [])
        error = item.get('error')

        if error:
            print(f"\n❌ {doc_id}: {error}")
            continue

        print(f"\n📄 {doc_id}")
        print(f"   共指簇 ({len(clusters)} 个):")

        for i, cluster in enumerate(clusters):
            if len(cluster) > 1:
                texts = [m['text'] for m in cluster]
                positions = [(m['char_start'], m['char_end']) for m in cluster]
                print(f"     簇 {i+1}: {texts}")
                print(f"         位置: {positions}")
            else:
                print(f"     簇 {i+1}: [{cluster[0]['text']}] (孤立)")
                print(f"         位置: ({cluster[0]['char_start']}, {cluster[0]['char_end']})")

    if len(results) > 5:
        print(f"\n... 还有 {len(results) - 5} 条结果，请查看 {results_file}")


def print_sample_output():
    """打印单条样本的输出格式示例"""
    print("\n" + "=" * 70)
    print("📝 输出格式示例")
    print("=" * 70)
    print("""
{
  "doc_id": "coref_test_001",
  "doc": "王芳邀请罗宾一同参加了项目评审会...",
  "mentions": [
    {"name": "王芳", "char_start": 0, "char_end": 2},
    {"name": "罗宾", "char_start": 4, "char_end": 6}
  ],
  "clusters": [
    [
      {"text": "王芳", "char_start": 0, "char_end": 2},
      {"text": "王芳", "char_start": 66, "char_end": 68}
    ],
    [
      {"text": "罗宾", "char_start": 4, "char_end": 6},
      {"text": "罗宾", "char_start": 45, "char_end": 47},
      {"text": "自己", "char_start": 51, "char_end": 53}
    ],
    [
      {"text": "这位记者", "char_start": 20, "char_end": 24}
    ],
    [
      {"text": "那位导演", "char_start": 32, "char_end": 36},
      {"text": "这位导演", "char_start": 69, "char_end": 73}
    ]
  ],
  "clusters_text": [
    ["王芳", "王芳"],
    ["罗宾", "罗宾", "自己"],
    ["这位记者"],
    ["那位导演", "这位导演"]
  ],
  "plural_pronouns": [],
  "pairwise_distances": [...],
  "threshold_used": 0.65
}
    """)


if __name__ == "__main__":

    # 打印格式示例
    print_sample_output()

    # 运行共指解析
    results = run_coreference_resolution(
        model_path='../models_cache/finetuned_paraphase',
        test_file='../data/coref_test.json',
        threshold=0.65,
        output_file='./reports/coref_results.json'
    )

    # 打印摘要
    print_summary('./reports/coref_results.json')