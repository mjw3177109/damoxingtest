"""Check public persona contract without loading private memory."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class MentorContractTests(unittest.TestCase):
    def test_bobo_is_explicit_mentor(self):
        ident = json.loads((ROOT / "identity.json").read_text(encoding="utf-8"))
        mentor = ident["relationship"]["mentor"]
        self.assertEqual(mentor["preferred_name"], "bobo")
        self.assertEqual(mentor["role"], "师傅")
        self.assertTrue(mentor["use_in_direct_dialogue"])
    def test_reflection_requires_real_user_reply(self):
        rules = json.loads((ROOT / "identity.json").read_text(encoding="utf-8"))["relationship"]["dialogue_policy"]
        self.assertIn("question", rules["daily_reflection"].lower())
        self.assertIn("do not invent replies", rules["reply_processing"].lower())
        self.assertIn("never publish private conversations", rules["privacy"].lower())
if __name__ == "__main__":
    unittest.main()
