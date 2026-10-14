"""Portable snapshot of the existing file verifier; no provider transcript adapter.

A file receipt proves byte equality at readback, not native AI memory adoption.
Contracts must come from the local dispatcher, never from a worker's reply.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time
from pathlib import Path

SCHEMA = "verified-handoff-files/v1"
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_REPORT_BYTES = 16384


def digest(value: dict) -> str:
    body = {k: v for k, v in value.items() if k != "manifest_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def fingerprint(path: Path) -> dict:
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
            raise ValueError("not_bounded_regular_file")
        h, size = hashlib.sha256(), 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                raise ValueError("file_too_large")
            h.update(chunk)
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("changed_during_read")
    return {"sha256": h.hexdigest(), "size": size}


def build_contract(run_id: str, source_paths: dict[str, Path], destination: Path) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id):
        raise ValueError("invalid_run_id")
    if not 1 <= len(source_paths) <= 16:
        raise ValueError("invalid_source_count")
    root = destination.expanduser().resolve()
    rows = []
    for key, raw in sorted(source_paths.items()):
        if not re.fullmatch(r"[a-z0-9_-]{1,50}", key):
            raise ValueError("invalid_source_key")
        entry = Path(raw).expanduser().absolute()
        path = entry.resolve(strict=True)
        if path == root or root in path.parents:
            raise ValueError("source_inside_destination")
        rows.append({"key": key, "source_path": str(path), "source_entry_path": str(entry), "target_name": key + ".snapshot",
                     **fingerprint(path)})
    contract = {"schema": SCHEMA, "run_id": run_id,
                "destination_root": str(root), "files": rows}
    contract["manifest_sha256"] = digest(contract)
    return contract


def prepare_contract(run_id: str, source_paths: dict[str, Path], run_root: Path) -> dict:
    """Seal this run's input inside its existing evidence directory, not a new SSOT.

    Existing run directories are never overwritten/replayed. A preparation failure
    leaves diagnostic evidence, sends nothing, and must use a fresh run on retry.
    """
    initial = build_contract(run_id, source_paths, run_root / "received")
    run_root = run_root.expanduser().resolve()
    run_root.mkdir(parents=True, exist_ok=False, mode=0o700)
    inputs = run_root / "inputs"
    inputs.mkdir(mode=0o700)
    sealed = {}
    for row in initial["files"]:
        target = inputs / row["target_name"]
        fd = os.open(row["source_path"], os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as src, target.open("xb") as dst:
            os.chmod(target, 0o600)
            if not stat.S_ISREG(os.fstat(src.fileno()).st_mode):
                raise ValueError("not_regular_source")
            remaining = row["size"] + 1
            while remaining:
                chunk = src.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                dst.write(chunk)
                remaining -= len(chunk)
            if remaining == 0:
                raise ValueError("source_grew_during_snapshot")
        if fingerprint(target) != {k: row[k] for k in ("sha256", "size")}:
            raise ValueError("source_changed_during_snapshot")
        sealed[row["key"]] = target
    contract = build_contract(run_id, sealed, run_root / "received")
    contract["origin_versions"] = initial["files"]
    contract["captured_at_ms"] = int(time.time() * 1000)
    contract["manifest_sha256"] = digest(contract)
    with (run_root / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(contract, stream, ensure_ascii=False, sort_keys=True)
        stream.write("\n")
    return contract


def verify_files(contract: dict) -> dict:
    result = {"status": "FILES_NOT_VERIFIED", "files_verified": False,
              "native_memory_verified": False, "checked": 0, "errors": []}
    try:
        if (contract.get("schema") != SCHEMA or digest(contract) != contract.get("manifest_sha256")
                or not 1 <= len(contract.get("files", [])) <= 16):
            raise ValueError("invalid_pinned_manifest")
        root = Path(contract["destination_root"])
        if not root.is_absolute() or root.resolve() != root:
            raise ValueError("destination_root_redirected")
        keys = set()
        for row in contract["files"]:
            key = row["key"]
            if (key in keys or not re.fullmatch(r"[a-z0-9_-]{1,50}", key)
                    or row["target_name"] != key + ".snapshot"):
                raise ValueError("invalid_target_binding")
            keys.add(key)
            expected = {k: row[k] for k in ("sha256", "size")}
            source, target = Path(row["source_path"]), root / row["target_name"]
            if source.resolve() != source:
                raise ValueError("source_redirected")
            if fingerprint(source) != expected:
                result["errors"].append({"key": key, "reason": "source_changed"})
                continue
            target_stat = target.lstat()
            if not stat.S_ISREG(target_stat.st_mode) or target_stat.st_nlink != 1:
                result["errors"].append({"key": key, "reason": "target_not_independent_copy"})
                continue
            if os.path.samefile(source, target):
                result["errors"].append({"key": key, "reason": "target_is_source"})
                continue
            if fingerprint(target) != expected:
                result["errors"].append({"key": key, "reason": "target_mismatch"})
                continue
            result["checked"] += 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        result["errors"].append({"reason": type(exc).__name__ + ":" + str(exc)[:180]})
    if not result["errors"]:
        result.update(status="FILES_VERIFIED_MEMORY_UNVERIFIED", files_verified=True)
        advanced = []
        for row in contract.get("origin_versions", []):
            try:
                current = Path(row.get("source_entry_path", row["source_path"])).resolve(strict=True)
                if current != Path(row["source_path"]) or fingerprint(current) != {k: row[k] for k in ("sha256", "size")}:
                    advanced.append(row["key"])
            except (OSError, ValueError, KeyError, RuntimeError):
                advanced.append(row.get("key", "unknown"))
        result.update(source_versions_current=not advanced, sources_advanced=advanced)
        if advanced:
            result["status"] = "FILES_VERIFIED_SOURCE_ADVANCED_MEMORY_UNVERIFIED"
    return result


def parse_receipt(text: str) -> dict:
    if len(text.encode()) > MAX_REPORT_BYTES:
        raise ValueError("report_too_large")
    blocks = re.findall(r"(?m)^VERIFIED_HANDOFF_V1\s*\n```json\s*\n([\s\S]*?)\n```", text)
    if len(blocks) != 1:
        raise ValueError("missing_or_ambiguous_structured_receipt")
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("duplicate_key")
            obj[key] = value
        return obj
    try:
        receipt = json.loads(blocks[0], object_pairs_hook=unique,
                             parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("invalid_json_receipt") from exc
    if not isinstance(receipt, dict):
        raise ValueError("invalid_json_receipt")
    if not isinstance(receipt.get("errors"), list) or any(not isinstance(x, str) for x in receipt["errors"]):
        raise ValueError("missing_or_invalid_errors")
    if receipt.get("phase") != "complete":
        raise ValueError("missing_final_phase")
    return receipt


def assess_report(contract: dict | None, run_id: str, agent_id: str,
                  sent_ms: int, text: str, meta: dict) -> dict:
    result = {"status": "REPORT_ONLY", "run_id": run_id, "files_verified": False,
              "native_memory_verified": False, "worker_terminal": False,
              "message_id": meta.get("selected_message_id")}
    ts = meta.get("selected_message_ts")
    if (meta.get("selected_agent_id") != agent_id or not result["message_id"]
            or type(ts) not in (int, float) or not sent_ms <= ts <= time.time() * 1000):
        return dict(result, status="IDENTITY_OR_TIME_MISMATCH")
    if not contract:
        return dict(result, reason="no_pinned_source_manifest")
    try:
        receipt = parse_receipt(text)
    except ValueError as exc:
        return dict(result, reason=str(exc))
    if (receipt.get("run_id") != run_id or contract.get("run_id") != run_id
            or receipt.get("manifest_sha256") != contract.get("manifest_sha256")):
        return dict(result, status="RECEIPT_BINDING_MISMATCH")
    result["worker_terminal"] = True
    if receipt["errors"]:
        return dict(result, status="WORKER_REPORTED_FAILURE", worker_errors=receipt["errors"][:8])
    return dict(result, **verify_files(contract))
