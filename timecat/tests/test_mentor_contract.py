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
    def test_mentor_first_value_hierarchy(self):
        ident = json.loads((ROOT / "identity.json").read_text(encoding="utf-8"))
        core = ident["core_principles"]
        self.assertEqual(core["value_priority"], ["尊师重道", "明理求真", "知行合一", "助手与工具（辅助）"])
        self.assertIn("辅助", core["auxiliary_role"])
        self.assertIn("不是人", core["guardrails"])
        self.assertTrue(ident["mission"][0].startswith("尊师重道"))
    def test_goals_prioritize_verified_mentor_guidance(self):
        goals = json.loads((ROOT / "goals.json").read_text(encoding="utf-8"))
        self.assertEqual(goals["long_term"][0]["id"], "G0")
        self.assertIn("approved", goals["long_term"][0]["evidence"])
        self.assertEqual(goals["long_term"][0]["status"], "in_progress")
if __name__ == "__main__":
    unittest.main()
