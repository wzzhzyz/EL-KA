import logging
import os

logging.disable(logging.CRITICAL)
os.environ["ELKA_LOG_LEVEL"] = "ERROR"

from entity_linker.pipeline import EntityLinkingPipeline

p = EntityLinkingPipeline(
    {
        "entity_alignment": {"enabled": True},
        "kb_path": "data/kb/energy_entities.json",
        "prefer_bge": True,
    }
)
print("backend=" + p.backend)
print(type(p.ner).__name__)
print(type(p.candidate_gen).__name__)
print(type(p.disambiguator).__name__)
print(type(p.vector_index).__name__)
