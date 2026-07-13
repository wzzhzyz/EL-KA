"""Regression tests for explicit coordinated collective coreference."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entity_linker.coreference import RuleBasedCoreferenceResolver


class CollectiveCoreferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = ROOT / "data" / "eval" / "coreference_collective_test.json"
        cls.samples = json.loads(path.read_text(encoding="utf-8"))["samples"]

    def test_collective_fixture(self) -> None:
        resolver = RuleBasedCoreferenceResolver()
        for sample in self.samples:
            with self.subTest(sample=sample["id"]):
                for mention in sample["mentions"]:
                    self.assertEqual(
                        sample["text"][mention["char_start"] : mention["char_end"]],
                        mention["mention"],
                    )
                resolutions = resolver.resolve(sample["mentions"], text=sample["text"])
                for expected in sample["expected_coreferences"]:
                    actual = resolutions[expected["mention_index"]]
                    self.assertEqual(actual.is_nil, expected["is_nil"])
                    self.assertEqual(
                        actual.is_collective,
                        expected["is_collective"],
                    )
                    self.assertEqual(actual.entity_id, expected["entity_id"])
                    self.assertEqual(set(actual.entity_ids), set(expected["entity_ids"]))
                    self.assertEqual(len(actual.entity_ids), len(set(actual.entity_ids)))

    def test_collective_serialization_keeps_legacy_entity_id(self) -> None:
        sample = self.samples[0]
        resolver = RuleBasedCoreferenceResolver()
        actual = resolver.resolve(sample["mentions"], text=sample["text"])[2].to_dict()
        self.assertIsNone(actual["entity_id"])
        self.assertEqual(
            actual["entity_ids"],
            ["TEST_PEOPLE_DAILY", "TEST_XINHUA"],
        )
        self.assertEqual(actual["antecedent_indices"], [0, 1])
        self.assertTrue(actual["is_collective"])
        self.assertFalse(actual["is_nil"])


if __name__ == "__main__":
    unittest.main()
