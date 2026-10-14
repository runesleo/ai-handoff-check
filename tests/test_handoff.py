"""Portable package tests. Only temporary synthetic files; no network/accounts."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "handoff.py"


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="handoff-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "context.txt"
        self.source.write_text("版本一\n", encoding="utf-8")
        self.asset = self.root / "asset.bin"
        self.asset.write_bytes(bytes(range(256)))

    def command(self, *args):
        env = dict(os.environ, PYTHONPATH="", PYTHONNOUSERSITE="1")
        return subprocess.run([sys.executable, "-B", str(CLI), *map(str, args)],
                              cwd=self.root, env=env, capture_output=True, text=True, timeout=15)

    def prepare(self):
        result = self.command("prepare", "--run-id", "example-1", "--run-root", self.root / "run",
                              "--source", f"context={self.source}", "--source", f"asset={self.asset}")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        manifest = json.loads(Path(output["manifest_path"]).read_text())
        return output, manifest

    def deliver(self, manifest):
        root = Path(manifest["destination_root"])
        root.mkdir()
        for row in manifest["files"]:
            shutil.copyfile(row["source_path"], root / row["target_name"])
        return root

    def verify(self, prepared, *args):
        return self.command("verify", "--manifest", prepared["manifest_path"],
                            "--expect-sha256", prepared["manifest_sha256"], *args)

    def test_skill_metadata_and_local_references(self):
        skill = (ROOT / "SKILL.md").read_text()
        self.assertTrue(skill.startswith("---\nname: ai-handoff-check\n"))
        self.assertIn("description: Use when", skill)
        self.assertIn("UNKNOWN_OUTCOME", skill)
        self.assertIn("native_memory_verified", skill)
        self.assertLess(len(skill.splitlines()), 160)
        for file in ("scripts/handoff.py", "scripts/core_sync_evidence.py", "scripts/demo.py", "references/protocol.md"):
            self.assertTrue((ROOT / file).is_file(), file)

    def test_help_works_outside_repository(self):
        result = self.command("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("prepare", result.stdout)

    def test_doctor_machine_readable_and_read_only(self):
        result = self.command("doctor", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "OK")
        self.assertTrue(report["read_only"])
        self.assertFalse(report["native_memory_verified"])
        self.assertTrue(all(item["status"] == "OK" for item in report["checks"]))
        self.assertFalse((self.root / "run").exists())

    def test_doctor_detects_incomplete_install(self):
        import importlib.util
        import unittest.mock
        cli_spec = importlib.util.spec_from_file_location("doctor_probe", CLI)
        module = importlib.util.module_from_spec(cli_spec)
        cli_spec.loader.exec_module(module)
        with unittest.mock.patch.object(module, "SKILL_ROOT", self.root):
            with unittest.mock.patch("sys.stdout", __import__("io").StringIO()) as output:
                result = module.main(["doctor", "--json"])
            report = json.loads(output.getvalue())
        self.assertEqual(result, 2)
        self.assertEqual(report["status"], "MISSING")
        self.assertTrue(any(item["status"] == "MISSING" for item in report["checks"]))

    def test_isolated_python_from_unrelated_directory(self):
        env = dict(os.environ, HOME=str(self.root), PYTHONPATH="", PYTHONNOUSERSITE="1")
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(CLI), "demo"],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["scope"], "local_fixture_only")

    def test_prepare_does_not_deliver(self):
        prepared, manifest = self.prepare()
        self.assertFalse(Path(manifest["destination_root"]).exists())
        self.assertFalse(prepared["files_verified"])
        self.assertEqual(self.verify(prepared).returncode, 2)

    def test_text_and_binary_delivery(self):
        prepared, manifest = self.prepare()
        self.deliver(manifest)
        result = self.verify(prepared, "--require-current")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["checked"], 2)
        self.assertTrue(value["files_verified"])
        self.assertFalse(value["native_memory_verified"])

    def test_current_source_is_separate_from_captured_delivery(self):
        prepared, manifest = self.prepare()
        self.deliver(manifest)
        self.source.write_text("版本二\n", encoding="utf-8")
        value = json.loads(self.verify(prepared).stdout)
        self.assertTrue(value["files_verified"])
        self.assertFalse(value["source_versions_current"])
        self.assertEqual(self.verify(prepared, "--require-current").returncode, 2)

    def test_corrupt_destination_is_rejected(self):
        prepared, manifest = self.prepare()
        (self.deliver(manifest) / "asset.snapshot").write_bytes(b"damaged")
        result = self.verify(prepared)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["files_verified"])

    def test_hardlink_to_original_is_not_a_copy(self):
        prepared, manifest = self.prepare()
        root = self.deliver(manifest)
        target = root / "context.snapshot"
        target.unlink()
        os.link(self.source, target)
        result = self.verify(prepared)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["files_verified"])

    def test_hardlink_to_same_content_third_file_is_not_a_copy(self):
        prepared, manifest = self.prepare()
        root = self.deliver(manifest)
        other = self.root / "third-copy.txt"
        other.write_bytes(self.source.read_bytes())
        target = root / "context.snapshot"
        target.unlink()
        os.link(other, target)
        result = self.verify(prepared)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["files_verified"])

    def test_fifo_manifest_fails_without_waiting_for_writer(self):
        fifo = self.root / "manifest.fifo"
        os.mkfifo(fifo)
        process = subprocess.run(
            [sys.executable, "-B", str(CLI), "verify",
             "--manifest", str(fifo), "--expect-sha256", "0" * 64],
            cwd=self.root, capture_output=True, text=True, timeout=3)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "INPUT_OR_IO_ERROR")

    def test_manifest_cannot_supply_its_own_trusted_hash(self):
        prepared, manifest = self.prepare()
        self.deliver(manifest)
        prepared["manifest_sha256"] = "0" * 64
        result = self.verify(prepared)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "MANIFEST_PIN_MISMATCH")

    def test_same_run_is_never_overwritten(self):
        self.prepare()
        result = self.command("prepare", "--run-id", "example-1", "--run-root", self.root / "run",
                              "--source", f"context={self.source}")
        self.assertEqual(result.returncode, 2)

    def test_duplicate_source_key_is_rejected(self):
        result = self.command("prepare", "--run-id", "example-1", "--run-root", self.root / "run",
                              "--source", f"context={self.source}", "--source", f"context={self.asset}")
        self.assertEqual(result.returncode, 2)

    def test_missing_errors_receipt_is_not_terminal(self):
        spec = importlib.util.spec_from_file_location("portable_evidence", ROOT / "scripts/core_sync_evidence.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(ValueError):
            module.parse_receipt('VERIFIED_HANDOFF_V1\n```json\n{"phase":"complete"}\n```')

    def test_symlink_loop_after_capture_is_stale_not_crash(self):
        import unittest.mock as mock
        spec = importlib.util.spec_from_file_location("loop_evidence", ROOT / "scripts/core_sync_evidence.py")
        ev = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ev)
        entry = self.root / "stable-entry"
        entry.symlink_to(self.source)
        result = self.command("prepare", "--run-id", "loop-run", "--run-root",
                              self.root / "loop-run", "--source", f"context={entry}")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(Path(json.loads(result.stdout)["manifest_path"]).read_text())
        self.deliver(manifest)
        original_resolve = Path.resolve
        def resolve(path, *args, **kwargs):
            if path == entry:
                raise RuntimeError("simulated symlink loop on Python 3.10")
            return original_resolve(path, *args, **kwargs)
        with mock.patch.object(Path, "resolve", resolve):
            checked = ev.verify_files(manifest)
        self.assertTrue(checked["files_verified"])
        self.assertFalse(checked["source_versions_current"])

    def test_symlink_loop_on_prepare_returns_json_error(self):
        import io
        import unittest.mock as mock
        spec = importlib.util.spec_from_file_location("loop_cli", CLI)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with mock.patch.object(Path, "resolve", side_effect=RuntimeError("simulated symlink loop")):
            with mock.patch("sys.stdout", io.StringIO()) as output:
                status = cli.main(["prepare", "--run-id", "loop-run", "--run-root",
                                   str(self.root / "loop-run"), "--source", f"context={self.source}"])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "INPUT_OR_IO_ERROR")

    def test_readme_leads_with_a_real_version_mismatch(self):
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh.md").read_text(encoding="utf-8")
        self.assertTrue(english.startswith("# AI Handoff Check"))
        self.assertIn("assets/handoff-flow.svg", english[:600])
        self.assertIn("brief.md", english)
        self.assertNotIn("brief_v2.md", english)
        self.assertNotIn("brief_v1.md", english)
        self.assertIn("same source path", english)
        self.assertIn("source v2, received v1", english)
        self.assertIn("demo/index.html", chinese)
        self.assertIn("不是一键同步器", chinese)

    def test_visual_assets_are_local_and_explain_the_three_checks(self):
        import xml.etree.ElementTree as ET
        image = ROOT / "assets" / "handoff-flow.svg"
        interactive = ROOT / "demo" / "index.html"
        self.assertTrue(image.is_file() and interactive.is_file())
        ET.parse(image)
        raw = image.read_text(encoding="utf-8")
        page = interactive.read_text(encoding="utf-8")
        self.assertIn("brief.md", raw)
        self.assertNotIn("brief_v2.md", raw)
        self.assertNotIn("brief_v1.md", raw)
        self.assertIn("SOURCE v2", raw)
        self.assertIn("RECEIVED v1", raw)
        self.assertIn("Latest version?", raw)
        self.assertIn("Needs a separate test", raw)
        for stage in ('data-stage="0"', 'data-stage="1"', 'data-stage="2"'):
            self.assertIn(stage, page)
        self.assertIn("network, or accounts", page)
        self.assertIn('href="https://github.com/runesleo/ai-handoff-check"', page)
        self.assertIn('href="https://github.com/runesleo/ai-handoff-check/blob/main/install.md"', page)
        self.assertNotIn('src="https://', page)
        self.assertNotIn("fetch(", page)
        self.assertIn("Separate output assertion", page)
        self.assertNotIn("brief_v1.md", page)
        self.assertNotIn("brief_v2.md", page)
        self.assertIn("brief.md", page)

    def test_demo_is_explicitly_offline(self):
        result = self.command("demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["scope"], "local_fixture_only")
        self.assertFalse(value["network_transport_tested"])
        self.assertFalse(value["native_memory_verified"])
        self.assertFalse(value["corrupt_target"]["files_verified"])


if __name__ == "__main__":
    unittest.main()
