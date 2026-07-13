from entity_linker.agents import default_pipeline_factory
from entity_linker.pipeline import EntityLinkingPipeline


def test_run_without_mentions_and_without_ner_fallback_returns_empty_result():
    pipeline = EntityLinkingPipeline({"entity_alignment": {"enabled": False}})

    result = pipeline.run(
        "国家电网发布了公告。",
        options={
            "enable_coreference": False,
            "allow_ner_fallback": False,
        },
        trace_id="test-no-mentions",
    )

    assert result["results"] == []
    assert result["stats"]["total_mentions"] == 0
    assert result["input_mode"] == "provided_mentions_required"


def test_run_with_mentions_includes_link_basis_metadata():
    pipeline = EntityLinkingPipeline({"entity_alignment": {"enabled": False}})

    result = pipeline.run(
        "国家电网发布了公告。",
        options={
            "mentions": [
                {
                    "mention": "国家电网",
                    "type": "ORG",
                    "char_start": 0,
                    "char_end": 4,
                    "confidence": 1.0,
                }
            ],
            "enable_coreference": False,
            "allow_ner_fallback": False,
        },
        trace_id="test-with-mentions",
    )

    assert result["results"]
    assert "link_basis" in result["results"][0]
    assert result["results"][0]["link_basis"]["source"] in {
        "candidate_generation",
        "disambiguation",
    }


def test_build_entity_alignment_config_uses_existing_kb_path_when_configured_path_missing():
    pipeline = EntityLinkingPipeline(
        {
            "entity_alignment": {"enabled": True},
            "kb_path": "data/missing_kb.json",
        }
    )

    config = pipeline._build_entity_alignment_config()

    assert config["knowledge_base"]["path"].endswith("data/kb/energy_entities.json")
    assert config["llm_fallback"]["enabled"] is False


def test_default_pipeline_factory_prefers_bge_backend():
    pipeline = default_pipeline_factory()

    assert pipeline.config["entity_alignment"]["enabled"] is True
    assert pipeline.config["prefer_bge"] is True
