from chinese_coref import ChineseCoreferenceResolver, Mention, render_resolutions


def build_sample_mentions():
    return [
        Mention(
            text="他",
            entity_type="PERSON",
            sentence_index=0,
            mention_role="pronoun",
        ),
        Mention(
            text="中国华能集团有限公司",
            entity_type="ORG",
            sentence_index=0,
            mention_role="name",
            linked_entity_id="ORG_001",
            aliases=("华能集团", "华能"),
        ),
        Mention(
            text="该集团",
            entity_type="ORG",
            sentence_index=0,
            mention_role="anaphor",
        ),
        Mention(
            text="公司",
            entity_type="ORG",
            sentence_index=0,
            mention_role="anaphor",
        ),
        Mention(
            text="张伟",
            entity_type="PERSON",
            sentence_index=1,
            mention_role="name",
            linked_entity_id="PER_001",
        ),
        Mention(
            text="他",
            entity_type="PERSON",
            sentence_index=1,
            mention_role="pronoun",
        ),
        Mention(
            text="北京大学",
            entity_type="ORG",
            sentence_index=2,
            mention_role="name",
            linked_entity_id="ORG_002",
            aliases=("北大",),
        ),
        Mention(
            text="该校",
            entity_type="ORG",
            sentence_index=2,
            mention_role="anaphor",
        ),
        Mention(
            text="它",
            entity_type="ORG",
            sentence_index=2,
            mention_role="pronoun",
        ),
    ]


def main():
    resolver = ChineseCoreferenceResolver(nil_threshold=0.55)
    results = resolver.resolve(build_sample_mentions())
    print(render_resolutions(results))

    assert results[1].antecedent_entity_id == "ORG_001"
    assert results[2].antecedent_entity_id == "ORG_001"
    assert results[4].antecedent_entity_id == "PER_001"
    assert results[6].antecedent_entity_id == "ORG_002"
    assert results[7].antecedent_entity_id == "ORG_002"
    assert results[0].is_nil is True


if __name__ == "__main__":
    main()
