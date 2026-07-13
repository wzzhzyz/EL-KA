import sys
import traceback

sys.path.insert(0, "EntityAlignmentV0")
from src.knowledge.kb_manager import KnowledgeBase

cfg = {
    "type": "json",
    "path": "D:/Doc/shixun/2/EL-KA/data/kb/kb_expansion_20260709_step1.json",
}
try:
    kb = KnowledgeBase(cfg)
    print("loaded", len(kb.get_all_entities()))
    print(kb.get_all_entities()[0].to_dict() if kb.get_all_entities() else "empty")
except Exception:
    traceback.print_exc()
