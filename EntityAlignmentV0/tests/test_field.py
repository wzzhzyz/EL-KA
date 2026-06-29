from dataclasses import dataclass


class BadMention:
    mention: str
    metadata: dict = {}  # ❌ 所有实例共享同一个 dict
    def __init__(self, mention):
        self.mention=mention

# 创建两个实例
m1 = BadMention("国网")
m2 = BadMention("南网")

# 修改 m1 的 metadata
m1.metadata["source"] = "NER"

# m2 的 metadata 也被污染了！
print(m2.metadata)  # {'source': 'NER'}  ← 不应该有！