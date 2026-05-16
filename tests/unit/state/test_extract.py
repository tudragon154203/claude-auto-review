import unittest

from claude_auto_review.state.hook_input import extract_file_paths_from_hook_input

from tests.unit.state.support import StateTestCase


class TestHookInputExtraction(StateTestCase, unittest.TestCase):

    def test_extracts_file_path_from_top_level(self):
        self.assertEqual(
            extract_file_paths_from_hook_input({"file_path": "a.ts"}), ["a.ts"]
        )

    def test_extracts_file_path_from_tool_input(self):
        self.assertEqual(
            extract_file_paths_from_hook_input({"tool_input": {"file_path": "b.ts"}}),
            ["b.ts"],
        )

    def test_extracts_unique_paths_only(self):
        payload = {
            "tool_input": {
                "file_path": "a.ts",
                "edits": [{"file_path": "a.ts"}, {"file_path": "b.ts"}],
            }
        }
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["a.ts", "b.ts"]
        )

    def test_extracts_paths_from_payload_directly_if_no_tool_input(self):
        payload = {"file_path": "direct.ts"}
        result = extract_file_paths_from_hook_input(payload)
        self.assertEqual(result, ["direct.ts"])

    def test_ignores_null_edit_entries(self):
        payload = {"tool_input": {"edits": [None, {"file_path": "a.ts"}]}}
        self.assertEqual(extract_file_paths_from_hook_input(payload), ["a.ts"])

    def test_ignores_null_values(self):
        payload = {"tool_input": {"file_path": None}}
        self.assertEqual(extract_file_paths_from_hook_input(payload), [])

    def test_handles_empty_tool_input(self):
        self.assertEqual(
            extract_file_paths_from_hook_input({"tool_input": {}}), []
        )

    def test_extracts_path_from_rm_command(self):
        payload = {"tool_input": {"command": 'rm "RULES-GUIDE.md"'}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["RULES-GUIDE.md"]
        )

    def test_extracts_all_paths_from_multi_rm(self):
        payload = {"tool_input": {"command": "rm a.ts b.ts c.ts"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["a.ts", "b.ts", "c.ts"]
        )

    def test_extracts_path_from_rm_with_flags(self):
        payload = {"tool_input": {"command": "rm -rf /tmp/build"}}
        self.assertEqual(extract_file_paths_from_hook_input(payload), ["/tmp/build"])

    def test_extracts_path_from_remove_item(self):
        payload = {"tool_input": {"command": 'Remove-Item -Path "test.txt" -Force'}}
        self.assertEqual(extract_file_paths_from_hook_input(payload), ["test.txt"])

    def test_extracts_path_from_del(self):
        payload = {"tool_input": {"command": "del /f cache.tmp"}}
        self.assertEqual(extract_file_paths_from_hook_input(payload), ["cache.tmp"])

    def test_extracts_path_from_echo_redirect(self):
        payload = {"tool_input": {"command": 'echo "hello" > output.txt'}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["output.txt"]
        )

    def test_extracts_destination_from_cp(self):
        payload = {"tool_input": {"command": "cp src.ts backup.ts"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["backup.ts"]
        )

    def test_extracts_source_and_destination_from_mv(self):
        payload = {"tool_input": {"command": "mv old.ts new.ts"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["old.ts", "new.ts"]
        )

    def test_extracts_multi_source_mv_destination_files(self):
        payload = {"tool_input": {"command": "mv old.ts other.ts src/"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload),
            ["old.ts", "other.ts", "src/old.ts", "src/other.ts"],
        )

    def test_extracts_mv_to_existing_directory_with_project_context(self):
        project_root = self.temp_project()
        (project_root / "src").mkdir()
        payload = {"tool_input": {"command": "mv old.ts src"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload, project_root=project_root),
            ["old.ts", "src/old.ts"],
        )

    def test_extracts_source_and_destination_from_move(self):
        payload = {"tool_input": {"command": "move old.ts new.ts"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["old.ts", "new.ts"]
        )

    def test_extracts_source_and_destination_from_move_item(self):
        payload = {"tool_input": {"command": "Move-Item old.ts new.ts"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["old.ts", "new.ts"]
        )

    def test_extracts_source_and_destination_from_git_mv(self):
        payload = {"tool_input": {"command": "git mv old.ts new.ts"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["old.ts", "new.ts"]
        )

    def test_extracts_from_git_mv_with_global_flags(self):
        payload = {"tool_input": {"command": "git -C /some/dir mv old.ts new.ts"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["old.ts", "new.ts"]
        )

    def test_extracts_source_and_destination_from_git_mv_with_flags(self):
        payload = {"tool_input": {"command": "git mv --force old.ts new.ts"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["old.ts", "new.ts"]
        )

    def test_extracts_multi_source_git_mv_destination_files(self):
        payload = {"tool_input": {"command": "git mv a.ts b.ts src/"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload),
            ["a.ts", "b.ts", "src/a.ts", "src/b.ts"],
        )

    def test_extracts_from_ren(self):
        payload = {"tool_input": {"command": "ren old.txt new.txt"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["old.txt", "new.txt"]
        )

    def test_extracts_from_rename_item(self):
        payload = {"tool_input": {"command": "Rename-Item -Path old.txt -NewName new.txt"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["old.txt", "new.txt"]
        )

    def test_extracts_path_from_touch(self):
        payload = {"tool_input": {"command": "touch deploy.lock"}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["deploy.lock"]
        )

    def test_extracts_path_from_script_key(self):
        payload = {"tool_input": {"script": 'Remove-Item "stale.log"'}}
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["stale.log"]
        )

    def test_extracts_from_both_command_and_script(self):
        payload = {
            "tool_input": {
                "command": 'rm "a.ts"',
                "script": 'Remove-Item "b.ts"',
            }
        }
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["a.ts", "b.ts"]
        )

    def test_skips_shell_flags_as_paths(self):
        payload = {"tool_input": {"command": "rm -rf -f"}}
        self.assertEqual(extract_file_paths_from_hook_input(payload), [])

    def test_no_paths_from_unrelated_command(self):
        payload = {"tool_input": {"command": "git status"}}
        self.assertEqual(extract_file_paths_from_hook_input(payload), [])

    def test_ignores_shell_words_inside_quoted_script_text(self):
        payload = {"tool_input": {"command": 'python -c "print(\'rm fake.ts\')"'}}
        self.assertEqual(extract_file_paths_from_hook_input(payload), [])

    def test_combined_file_path_and_command(self):
        payload = {
            "tool_input": {"file_path": "a.ts", "command": 'rm "b.ts"'}
        }
        self.assertEqual(
            extract_file_paths_from_hook_input(payload), ["a.ts", "b.ts"]
        )


if __name__ == "__main__":
    unittest.main()
