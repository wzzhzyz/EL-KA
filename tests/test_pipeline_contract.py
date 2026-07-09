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
