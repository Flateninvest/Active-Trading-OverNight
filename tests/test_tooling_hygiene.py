"""Strict evidence parsing and reproducible public packaging, with synthetic inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from active_trading.jsonio import StrictJSONError, load_json, loads_json
from active_trading.research.protocol import ProtocolError, read_ledger
from scripts import validate_portable
from scripts.package_review_pack import package_review_pack


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True).stdout


def repository(path):
    path.mkdir()
    git(path, "init")
    (path / ".gitignore").write_bytes(b".runtime/\n")
    (path / "document.md").write_bytes(b"# Synthetic document\n[Other](other.md)\n")
    (path / "historical.json").write_bytes(b'{"historical":true}\n')
    git(path, "add", ".")
    git(path, "-c", "user.name=Synthetic Test", "-c", "user.email=synthetic@example.invalid",
        "-c", "core.autocrlf=false", "commit", "-m", "Synthetic fixture")
    return path


class ToolingHygieneTests(unittest.TestCase):
    def test_prompt_directory_has_one_effective_prompt_and_five_labelled_archives(self):
        paths = sorted((ROOT / "prompts").glob("*.txt"))
        current = ROOT / "prompts" / "Grok_Overnight_Stock_Bot_Prompt_Current.txt"
        effective = [path for path in paths if not path.read_text(encoding="utf-8").startswith("ARCHIVED")]
        self.assertEqual(effective, [current])
        archives = [path for path in paths if path != current]
        self.assertEqual(len(archives), 5)
        for path in archives:
            with self.subTest(path=path.name):
                self.assertTrue(path.read_text(encoding="utf-8").startswith("ARCHIVED"))

    def test_prompt_guides_point_to_current_prompt_and_shared_specification(self):
        for name in ("README.md", "GROK_SETUP.md"):
            text = (ROOT / "prompts" / name).read_text(encoding="utf-8")
            with self.subTest(guide=name):
                self.assertIn("Grok_Overnight_Stock_Bot_Prompt_Current.txt", text)
                self.assertIn("strategy_spec.provisional.json", text)

    def test_effective_prompt_utf8_and_all_seven_stages_are_preserved(self):
        text = (ROOT / "prompts" / "Grok_Overnight_Stock_Bot_Prompt_Current.txt").read_bytes().decode("utf-8")
        self.assertNotIn("\ufffd", text)
        self.assertNotIn("â€", text)
        self.assertIn("—", text)
        self.assertIn("2–10", text)
        for number in range(1, 8):
            with self.subTest(stage=number):
                self.assertRegex(text, rf"(?m)^{number}\. [A-Z]")

    def test_rejects_duplicate_keys_at_every_depth(self):
        for raw in ('{"mode":"DEMO","mode":"LIVE"}', '{"risk":{"limit":1,"limit":2}}',
                    '[{"fee":"0","fee":"2"}]'):
            with self.subTest(raw=raw), self.assertRaises(StrictJSONError):
                loads_json(raw)

    def test_rejects_nonfinite_constants_and_overflow_numbers(self):
        for raw in ('{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}', '{"a":1e9999}'):
            with self.subTest(raw=raw), self.assertRaises(StrictJSONError):
                loads_json(raw)

    def test_loads_utf8_bom_and_preserves_valid_json(self):
        with tempfile.TemporaryDirectory(prefix="json-hygiene-", dir=ROOT.parent) as folder:
            path = Path(folder) / "synthetic.json"
            path.write_bytes(b'\xef\xbb\xbf{"limit":0.1,"quantity":"0.2"}')
            self.assertEqual(load_json(path), {"limit": 0.1, "quantity": "0.2"})

    def test_research_ledger_refuses_duplicate_keys_before_chain_validation(self):
        with tempfile.TemporaryDirectory(prefix="json-hygiene-", dir=ROOT.parent) as folder:
            path = Path(folder) / "synthetic.jsonl"
            path.write_text('{"type":"TRIAL_RESULT","type":"TRIAL_STARTED"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ProtocolError, "invalid event"):
                read_ledger(path)

    def test_earnings_and_research_clis_refuse_duplicate_keys(self):
        with tempfile.TemporaryDirectory(prefix="json-hygiene-", dir=ROOT.parent) as folder:
            source, output = Path(folder) / "input.json", Path(folder) / "output.json"
            source.write_text('{"mode":"DEMO","mode":"LIVE"}', encoding="utf-8")
            commands = (
                ["earnings_plan.py", "--input", str(source), "--output", str(output)],
                ["research_loop.py", "validate", "--plan", str(source)],
            )
            for command in commands:
                with self.subTest(command=command[0]):
                    result = subprocess.run([sys.executable, str(ROOT / "scripts" / command[0]), *command[1:]],
                                            cwd=ROOT, capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(output.exists())

    def test_default_validation_record_does_not_change_git_status_or_tracked_evidence(self):
        with tempfile.TemporaryDirectory(prefix="runner-hygiene-", dir=ROOT.parent) as folder:
            repo = repository(Path(folder) / "repo")
            before = git(repo, "status", "--porcelain")
            original = (repo / "historical.json").read_bytes()
            with patch.object(validate_portable, "ROOT", repo):
                output = validate_portable.save_record({"synthetic": True})
            self.assertEqual(output, repo / ".runtime" / "portable" / "check-result.json")
            self.assertTrue(output.exists())
            self.assertEqual((repo / "historical.json").read_bytes(), original)
            self.assertEqual(git(repo, "status", "--porcelain"), before)

    def test_validation_refuses_tracked_output_and_existing_explicit_output(self):
        with tempfile.TemporaryDirectory(prefix="runner-hygiene-", dir=ROOT.parent) as folder:
            repo = repository(Path(folder) / "repo")
            path = repo / "historical.json"
            original = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "tracked"):
                validate_portable.save_record({"bad": True}, path)
            self.assertEqual(path.read_bytes(), original)
            new = Path(folder) / "new.json"
            validate_portable.save_record({"synthetic": True}, new)
            with self.assertRaisesRegex(ValueError, "new file"):
                validate_portable.save_record({"bad": True}, new)

    def test_runner_refuses_unsafe_output_before_loading_suites(self):
        with patch.object(validate_portable.unittest.TestLoader, "discover") as discover:
            with self.assertRaisesRegex(ValueError, "tracked"):
                validate_portable.main(["--output", str(ROOT / "docs" / "portable-check-result.json")])
            discover.assert_not_called()

    def test_validation_output_cannot_write_git_metadata(self):
        with self.assertRaisesRegex(ValueError, "Git metadata"):
            validate_portable.save_record({"bad": True}, ROOT / ".git" / "new-evidence.json")

    def test_manifest_uses_committed_blob_even_when_worktree_has_crlf(self):
        with tempfile.TemporaryDirectory(prefix="pack-hygiene-", dir=ROOT.parent) as folder:
            repo = repository(Path(folder) / "repo")
            committed = git(repo, "cat-file", "blob", "HEAD:document.md")
            (repo / "document.md").write_bytes(committed.replace(b"\n", b"\r\n"))
            output = Path(folder) / "review.zip"
            result = package_review_pack(output, repo=repo, paths=("document.md",))
            with ZipFile(output) as archive:
                manifest = loads_json(archive.read("manifest.json"))
                item = manifest["contents"][0]
                self.assertEqual(archive.read("document.md"), committed)
                self.assertEqual(item["repository_bytes_sha256"], hashlib.sha256(committed).hexdigest())
                self.assertEqual(item["download_bytes_sha256"], hashlib.sha256(archive.read("document.md")).hexdigest())
            self.assertEqual(result["zip_bytes_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())

    def test_portable_markdown_download_hash_matches_transformed_archive_bytes(self):
        with tempfile.TemporaryDirectory(prefix="pack-hygiene-", dir=ROOT.parent) as folder:
            repo = repository(Path(folder) / "repo")
            output = Path(folder) / "review.zip"
            result = package_review_pack(output, repo=repo, paths=("document.md",), portable_markdown=True)
            with ZipFile(output) as archive:
                manifest = loads_json(archive.read("manifest.json"))
                item = manifest["contents"][0]
                raw = archive.read("document.md")
                self.assertIn(result["source_commit"].encode("ascii"), raw)
                self.assertNotEqual(item["repository_bytes_sha256"], item["download_bytes_sha256"])
                self.assertEqual(item["download_bytes_sha256"], hashlib.sha256(raw).hexdigest())

    def test_package_refuses_git_output_and_existing_zip(self):
        with tempfile.TemporaryDirectory(prefix="pack-hygiene-", dir=ROOT.parent) as folder:
            repo = repository(Path(folder) / "repo")
            with self.assertRaisesRegex(ValueError, "outside"):
                package_review_pack(repo / "review.zip", repo=repo, paths=("document.md",))
            output = Path(folder) / "review.zip"
            package_review_pack(output, repo=repo, paths=("document.md",))
            with self.assertRaises(FileExistsError):
                package_review_pack(output, repo=repo, paths=("document.md",))

    def test_package_refuses_reserved_manifest_path(self):
        with tempfile.TemporaryDirectory(prefix="pack-hygiene-", dir=ROOT.parent) as folder:
            repo = repository(Path(folder) / "repo")
            with self.assertRaisesRegex(ValueError, "Unique"):
                package_review_pack(Path(folder) / "review.zip", repo=repo, paths=("manifest.json",))


if __name__ == "__main__":
    unittest.main()
