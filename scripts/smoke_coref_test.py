import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json

from entity_linker.pipeline import EntityLinkingPipeline
from entity_linker.utils.trace import new_trace_id

pipeline = EntityLinkingPipeline({"entity_alignment": {"enabled": False}})
text = "国家电网发布了公告。它表示将加大投资。"
mentions = [
    {
        "mention": "国家电网",
        "type": "ORG",
        "char_start": 0,
        "char_end": 4,
        "confidence": 1.0,
        "metadata": {"sentence_index": 0},
    },
    {
        "mention": "它",
        "type": "PRON",
        "char_start": 7,
        "char_end": 8,
        "confidence": 1.0,
        "metadata": {"sentence_index": 1},
    },
]

res = pipeline.run_with_mentions(
    text=text,
    mentions=mentions,
    options={"enable_coreference": True},
    trace_id=new_trace_id(prefix="test-coref"),
)
print(json.dumps(res, ensure_ascii=False, indent=2))
