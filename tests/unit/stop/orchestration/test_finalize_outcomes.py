import unittest
from types import SimpleNamespace

from claude_auto_review.stop.orchestration.finalize_outcomes import (
    FinalizeEffect,
    artifact_status_name,
    plan_for_artifact_state,
    plan_for_invalid_settings,
    plan_for_partial_review,
    plan_for_pending_review,
)
from claude_auto_review.stop.orchestration.resolution import FinalizeAction


class TestFinalizeOutcomes(unittest.TestCase):
    def test_artifact_status_name_handles_enum_like_status(self):
        artifact_state = SimpleNamespace(status=SimpleNamespace(value="complete_clean"))
        self.assertEqual(artifact_status_name(artifact_state), "complete_clean")

    def test_complete_clean_maps_to_apply_plan(self):
        plan = plan_for_artifact_state(SimpleNamespace(status="complete_clean"))
        self.assertEqual(plan.effect, FinalizeEffect.APPLY_COMPLETED_CLEAN_REVIEW)
        self.assertEqual(plan.result.action, FinalizeAction.APPROVED)

    def test_complete_findings_maps_to_block_plan(self):
        plan = plan_for_artifact_state(SimpleNamespace(status="complete_findings"))
        self.assertEqual(plan.effect, FinalizeEffect.RECORD_FINDINGS_BLOCK)
        self.assertEqual(plan.result.action, FinalizeAction.BLOCKED_FINDINGS)

    def test_pending_returns_no_plan(self):
        self.assertIsNone(plan_for_artifact_state(SimpleNamespace(status="pending")))

    def test_specialized_block_plans_keep_expected_actions(self):
        self.assertEqual(plan_for_invalid_settings().result.action, FinalizeAction.BLOCKED_INVALID_SETTINGS)
        self.assertEqual(plan_for_partial_review().result.action, FinalizeAction.BLOCKED_PARTIAL_REVIEW)
        self.assertEqual(plan_for_pending_review().result.action, FinalizeAction.BLOCKED_PENDING)


if __name__ == "__main__":
    unittest.main()
