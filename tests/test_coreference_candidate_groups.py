"""Unit tests for internal coordinated-group exposure compatibility."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entity_linker.coreference import CoreferenceMention, RuleBasedCoreferenceResolver


def mention(text: str, surface: str, entity_id: str | None, start_at: int = 0, kind: str = "ORG") -> dict:
    start = text.index(surface, start_at)
    return {
        "mention": surface,
        "type": kind,
        "char_start": start,
        "char_end": start + len(surface),
        "role": "name" if entity_id else "pronoun",
        "entity_id": entity_id,
        "sentence_index": 0,
    }


class CandidateGroupExposureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = RuleBasedCoreferenceResolver()

    def _candidates(self, text: str, items: list[dict], target_index: int):
        mentions = [CoreferenceMention.from_dict(item) for item in items]
        return self.resolver._collect_coordinated_group_candidates(text, target_index, mentions)

    def test_single_two_entity_group(self) -> None:
        text = "甲公司和乙公司发布公告，双方继续合作。"
        items = [mention(text, "甲公司", "E1"), mention(text, "乙公司", "E2"), mention(text, "双方", None)]
        candidates = self._candidates(text, items, 2)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].entity_ids, ("E1", "E2"))
        self.assertEqual(candidates[0].mention_indices, (0, 1))

    def test_three_entity_group_is_complete(self) -> None:
        text = "甲局、乙局以及丙局共同部署，三方分别落实。"
        items = [
            mention(text, "甲局", "E1"),
            mention(text, "乙局", "E2"),
            mention(text, "丙局", "E3"),
            mention(text, "三方", None),
        ]
        candidates = self._candidates(text, items, 3)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].entity_ids, ("E1", "E2", "E3"))

    def test_multiple_groups_keep_text_order_and_public_rule_keeps_last(self) -> None:
        text = "甲公司和乙公司达成合作，丙公司与丁公司签署协议，双方公布安排。"
        items = [
            mention(text, "甲公司", "E1"),
            mention(text, "乙公司", "E2"),
            mention(text, "丙公司", "E3"),
            mention(text, "丁公司", "E4"),
            mention(text, "双方", None),
        ]
        mentions = [CoreferenceMention.from_dict(item) for item in items]
        candidates = self.resolver._collect_coordinated_group_candidates(text, 4, mentions)
        public_group = self.resolver.find_collective_antecedents(text, 4, mentions)
        self.assertEqual([candidate.entity_ids for candidate in candidates], [("E1", "E2"), ("E3", "E4")])
        self.assertEqual([index for index, _ in public_group], list(candidates[-1].mention_indices))
        resolution = self.resolver.resolve(items, text=text)[4]
        self.assertEqual(resolution.entity_ids, ["E3", "E4"])
        self.assertEqual(resolution.rule, "collective_coordinated_antecedents")
        self.assertEqual(resolution.confidence, 0.9)

    def test_invalid_groups_are_filtered(self) -> None:
        text = "甲公司和乙公司、丙公司与它们、北京和上海、丁公司和戊公司发布公告，双方回应。"
        items = [
            mention(text, "甲公司", "E1"),
            mention(text, "乙公司", None),
            mention(text, "丙公司", "E3"),
            mention(text, "它们", None),
            mention(text, "北京", "E4", kind="GPE"),
            mention(text, "上海", "E5", kind="GPE"),
            mention(text, "丁公司", "E6"),
            mention(text, "戊公司", "E6"),
            mention(text, "双方", None),
        ]
        candidates = self._candidates(text, items, 8)
        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
