import json
from typing import List, Dict, Set, Tuple, Any


# --- 1. 定义共指消解模块的接口 (假设为 Coreference) ---
# 您需要在这个模块中实现您的共指消解算法
class Coreference:
    """
    共指消解类 (假设的实现接口)
    输入: text (str), mentions (List[Dict[str, Any]])
    输出: 共指链 (List[List[Dict[str, Any]]])
    """

    def __init__(self):
        # 初始化您的模型或配置
        pass

    def predict(self, text: str, mentions: List[Dict]) -> List[List[Dict]]:
        """
        对给定的文本和提及列表进行共指消解。

        参数:
            text: 输入文本。
            mentions: 一个词典列表，每个词典代表一个提及，必须包含 'name', 'char_start', 'char_end' 键。

        返回:
            一个列表，包含多个共指链，每个共指链是一个提及词典的列表。
        """
        # 注意: 这里的 mentions 输入是未分组的，需要您自行处理
        # 1. 根据 char_start 对 mentions 排序（如果算法需要）
        # 2. 执行共指消解逻辑
        # 3. 返回共指链列表

        # 这是一个占位实现，仅用于演示，它会为每个提及创建一个独立的链
        # 您需要将其替换为您的实际模型推理代码
        print(f"警告: 正在使用 Coreference 类的默认占位实现。")
        return [[mention] for mention in mentions]


# --- 2. 辅助函数: 比较两个共指链是否等价 (忽略提及顺序) ---
def normalize_chain(chain: List[Dict]) -> Set[Tuple[str, int, int]]:
    """
    将共指链转换为一个由 (name, char_start, char_end) 组成的集合，用于比较。
    """
    return {(mention['name'], mention['char_start'], mention['char_end']) for mention in chain}


def are_clusters_equivalent(actual_clusters: List[List[Dict]],
                            expected_clusters: List[List[Dict]]) -> bool:
    """
    检查两个共指链列表是否包含相同的链集合，忽略链内和链间的提及顺序。
    """
    # 标准化每个链，然后转换为一个 frozenset 的集合，以便进行比较
    actual_set = {frozenset(normalize_chain(chain)) for chain in actual_clusters}
    expected_set = {frozenset(normalize_chain(chain)) for chain in expected_clusters}

    return actual_set == expected_set


# --- 3. 核心测试函数 ---
def run_coref_tests(test_data_file: str, coref_model: Coreference):
    """
    运行共指消解测试，并打印所有失败的用例。

    参数:
        test_data_file: 包含测试数据的 JSON 文件路径。
        coref_model: Coreference 类的实例。
    """
    # 加载测试数据
    with open(test_data_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    total_tests = 0
    failed_tests = 0

    # 用于存储所有失败的用例详情
    failed_cases = []

    for i, test_case in enumerate(test_data):
        doc_id = test_case.get('doc_id', f'未命名文档_{i}')
        text = test_case['doc']
        expected_clusters = test_case['clusters']

        # 从预期共指链中提取所有唯一的 mentions
        all_mentions = []
        seen_mentions = set()
        for cluster in expected_clusters:
            for mention in cluster:
                # 使用 (name, char_start, char_end) 作为唯一标识
                mention_key = (mention['name'], mention['char_start'], mention['char_end'])
                if mention_key not in seen_mentions:
                    seen_mentions.add(mention_key)
                    all_mentions.append(mention.copy())  # 添加副本，避免修改原数据

        # 调用模型进行预测
        try:
            predicted_clusters = coref_model.predict(text, all_mentions)
            total_tests += 1
        except Exception as e:
            print(f"\n--- 文档 '{doc_id}' 预测失败 ---")
            print(f"错误信息: {e}")
            failed_tests += 1
            failed_cases.append({
                'doc_id': doc_id,
                'text': text,
                'mentions': all_mentions,
                'expected_clusters': expected_clusters,
                'predicted_clusters': None,
                'error': str(e)
            })
            continue

        # 比较预测结果和预期结果
        if not are_clusters_equivalent(predicted_clusters, expected_clusters):
            failed_tests += 1
            failed_cases.append({
                'doc_id': doc_id,
                'text': text,
                'mentions': all_mentions,
                'expected_clusters': expected_clusters,
                'predicted_clusters': predicted_clusters,
                'error': None
            })

    # --- 4. 输出所有失败用例 ---
    if failed_cases:
        print(f"\n{'=' * 80}")
        print(f"共发现 {len(failed_cases)} 个失败用例 (总计 {total_tests} 个测试)")
        print(f"{'=' * 80}")

        for idx, case in enumerate(failed_cases):
            print(f"\n--- 失败用例 #{idx + 1} ---")
            print(f"文档 ID: {case['doc_id']}")
            print(f"文本: {case['text']}")
            print(f"\n提及列表 (模型输入):")
            for mention in case['mentions']:
                print(f"  - 名称: '{mention['name']}', 起始: {mention['char_start']}, 结束: {mention['char_end']}")

            print(f"\n预期共指链:")
            for chain in case['expected_clusters']:
                chain_str = " -> ".join([f"{m['name']}({m['char_start']}-{m['char_end']})" for m in chain])
                print(f"  [ {chain_str} ]")

            if case.get('error'):
                print(f"\n预测失败，错误信息: {case['error']}")
            else:
                print(f"\n实际共指链 (模型输出):")
                for chain in case['predicted_clusters']:
                    chain_str = " -> ".join([f"{m['name']}({m['char_start']}-{m['char_end']})" for m in chain])
                    print(f"  [ {chain_str} ]")

            print("-" * 40)
    else:
        if total_tests > 0:
            print(f"\n所有 {total_tests} 个测试用例均通过！")
        else:
            print("\n没有执行任何测试，请检查数据文件是否为空或格式是否正确。")


# --- 5. 示例运行 (如何使用) ---
if __name__ == "__main__":
    # 1. 假设您的数据文件名为 'coref_train_data2.json'
    test_file_path = 'coref_train_data2.json'  # 请确认文件路径正确

    # 2. 实例化您的共指消解模型
    # 注意: 这里使用占位类，您应该替换为您自己实现的类
    my_coref_model = Coreference()

    # 3. 运行测试
    run_coref_tests(test_file_path, my_coref_model)