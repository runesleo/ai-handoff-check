"""Bounded local handoff CLI. No network, accounts, scheduler or memory API."""
from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path
import re
import stat
import sys

VERSION = "0.1.0"
SKILL_ROOT = Path(__file__).resolve().parents[1]
MAX_MANIFEST_BYTES = 128 * 1024


def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def read_manifest(path: Path) -> dict:
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("manifest_not_regular_file")
        if info.st_size > MAX_MANIFEST_BYTES:
            raise ValueError("manifest_too_large")
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("manifest_too_large")
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate_manifest_key")
            value[key] = item
        return value
    def reject_constant(value):
        raise ValueError("nonfinite_manifest_value")
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("manifest_not_object")
    return value


def doctor_report() -> dict:
    """Inspect only; no provider accounts, network, writes or imported adapters."""
    definitions = [
        ("python", sys.version_info >= (3, 10), "Install Python 3.10+"),
        ("skill_definition", (SKILL_ROOT / "SKILL.md").is_file(), "Restore the complete Skill directory"),
        ("verifier", (SKILL_ROOT / "scripts/core_sync_evidence.py").is_file(), "Restore scripts/core_sync_evidence.py"),
        ("offline_demo", (SKILL_ROOT / "scripts/demo.py").is_file(), "Restore scripts/demo.py"),
        ("protocol", (SKILL_ROOT / "references/protocol.md").is_file(), "Restore references/protocol.md"),
        ("installation_guide", (SKILL_ROOT / "install.md").is_file(), "Restore install.md"),
    ]
    checks = [{"id": key, "status": "OK" if ready else "MISSING",
               "owner": "none" if ready else "agent", "next_action": "" if ready else action}
              for key, ready, action in definitions]
    return {"status": "OK" if all(ready for _, ready, _ in definitions) else "MISSING",
            "read_only": True, "native_memory_verified": False, "checks": checks}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("demo", help="run an offline synthetic-file example")
    doctor = commands.add_parser("doctor", help="read-only local installation check")
    doctor.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    prepare = commands.add_parser("prepare", help="create snapshots; does not send files")
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--run-root", required=True, type=Path)
    prepare.add_argument("--source", action="append", required=True, metavar="NAME=PATH")
    verify = commands.add_parser("verify", help="read back files against a controller-pinned manifest")
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--expect-sha256", required=True, help="hash saved by the controller before dispatch")
    verify.add_argument("--require-current", action="store_true", help="also reject an advanced original source")
    args = parser.parse_args(argv)
    try:
        if args.action == "doctor":
            report = doctor_report()
            emit(report)
            return 0 if report["status"] == "OK" else 2
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import core_sync_evidence as evidence
        if args.action == "demo":
            from demo import demo
            emit(demo())
            return 0
        if args.action == "prepare":
            sources = {}
            for item in args.source:
                key, separator, value = item.partition("=")
                if not separator or not value or key in sources:
                    raise ValueError("invalid_or_duplicate_source")
                sources[key] = Path(value)
            contract = evidence.prepare_contract(args.run_id, sources, args.run_root)
            emit({"status": "PREPARED_NOT_SENT", "run_id": contract["run_id"],
                  "manifest_path": str(args.run_root.expanduser().resolve() / "manifest.json"),
                  "manifest_sha256": contract["manifest_sha256"], "files_verified": False,
                  "native_memory_verified": False})
            return 0
        if not re.fullmatch(r"[0-9a-f]{64}", args.expect_sha256):
            raise ValueError("invalid_expected_sha256")
        contract = read_manifest(args.manifest)
        if not hmac.compare_digest(evidence.digest(contract), args.expect_sha256):
            emit({"status": "MANIFEST_PIN_MISMATCH", "files_verified": False,
                  "native_memory_verified": False})
            return 2
        result = evidence.verify_files(contract)
        accepted = result["files_verified"] and (not args.require_current or result.get("source_versions_current") is True)
        result["requested_checks_passed"] = bool(accepted)
        emit(result)
        return 0 if accepted else 2
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, RecursionError) as exc:
        emit({"status": "INPUT_OR_IO_ERROR", "reason": type(exc).__name__ + ":" + str(exc)[:240],
              "files_verified": False, "native_memory_verified": False})
        return 2


if __name__ == "__main__":
    sys.exit(main())
