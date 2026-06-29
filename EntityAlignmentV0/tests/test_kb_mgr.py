from src.knowledge.kb_manager import KnowledgeBase
from src.utils.config import load_config

config = load_config()
kb = KnowledgeBase(config["knowledge_base"])

# 查询
entity = kb.get_entity_by_alias("国网")
print(entity.standard_name)  # 国家电网有限公司

# 获取所有实体
all_entities = kb.get_all_entities()

# 统计
stats = kb.get_stats()
print(stats)