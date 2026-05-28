from tests.e2e.support import EndToEndTestCase


class EndToEndCorruptStateTests(EndToEndTestCase):
    def test_corrupt_jsonl_allows_stop(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("const x = 1;\n", encoding="utf-8")

        self.track(project_root, "src/app.ts")

        from claude_auto_review.runtime.client_dirs import client_state_path

        state_path = client_state_path(project_root, "test-session")
        state_path.write_text(
            "{bad json\nnot json at all\n",
            encoding="utf-8",
        )

        stop = self.stop(project_root, use_fake_claude=False, env_overrides={"PATH": ""})
        self.assertEqual(stop.returncode, 0, "Corrupt state should fail open and allow stop")

    def test_partial_corrupt_jsonl_keeps_valid_entries(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("const x = 1;\n", encoding="utf-8")

        self.track(project_root, "src/app.ts")

        from claude_auto_review.runtime.client_dirs import client_state_path
        from claude_auto_review.state.store.read import load_state

        state_path = client_state_path(project_root, "test-session")
        state_path.write_text(
            'not-json\n{"type":"edit","file":"src/app.ts","hash":"abc12345","timestamp":"2026-01-01","reviewed":false}\nalso-bad\n',
            encoding="utf-8",
        )

        state = load_state(project_root, "test-session")
        self.assertEqual(len(state), 1)
        self.assertEqual(state[0].file, "src/app.ts")

    def test_missing_state_file_allows_stop(self):
        project_root = self.temp_project()

        stop = self.stop(project_root, use_fake_claude=False, env_overrides={"PATH": ""})
        self.assertEqual(stop.returncode, 0, "Missing state should allow stop")
