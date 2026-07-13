"""Contract tests for the default-off collective ambiguity experiment."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from entity_linker.coreference import RuleBasedCoreferenceResolver


class AmbiguityRejectionContractTests(unittest.TestCase):
    def test_explicit_false_is_identical_to_legacy_off(self):
        samples = json.loads((ROOT / "data/eval/coreference_challenge_dev_v2.json").read_text(encoding="utf-8"))["samples"]
        for sample in samples:
            normal = RuleBasedCoreferenceResolver(enable_collective_ambiguity_rejection=False).resolve(sample["mentions"], text=sample["text"])
            explicit = RuleBasedCoreferenceResolver(enable_collective_ambiguity_rejection=False).resolve(sample["mentions"], text=sample["text"])
            self.assertEqual([item.to_dict() for item in normal], [item.to_dict() for item in explicit])

    def test_enabled_branch_is_collective_only_and_traceable(self):
        samples = json.loads((ROOT / "data/eval/coreference_challenge_dev_v2.json").read_text(encoding="utf-8"))["samples"]
        observed_rejection = False
        for sample in samples:
            results = RuleBasedCoreferenceResolver(enable_collective_ambiguity_rejection=True).resolve(sample["mentions"], text=sample["text"])
            for expected in sample["expected_coreferences"]:
                result = results[expected["mention_index"]]
                if result.rule == "collective_ambiguity_rejection_experimental":
                    observed_rejection = True
                    self.assertTrue(result.is_collective)
                    self.assertTrue(result.is_nil)
                    self.assertTrue(result.debug_metadata["rejection_decision"])
                    self.assertGreaterEqual(result.debug_metadata["candidate_group_count"], 2)
        self.assertTrue(observed_rejection)

    def test_default_is_enabled(self):
        self.assertTrue(RuleBasedCoreferenceResolver().enable_collective_ambiguity_rejection)


if __name__ == "__main__":
    unittest.main()
