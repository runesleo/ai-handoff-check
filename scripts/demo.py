"""Offline synthetic-file demonstration; no AI, network or account calls."""
import json
from pathlib import Path
import shutil
import tempfile

from core_sync_evidence import prepare_contract, verify_files


def demo():
    with tempfile.TemporaryDirectory(prefix="handoff-demo-") as tmp:
        root = Path(tmp)
        text, binary = root / "context.md", root / "asset.bin"
        text.write_text("Language: Chinese\nTask version: 1\n", encoding="utf-8")
        binary.write_bytes(bytes(range(256)) * 32)
        contract = prepare_contract("demo-v1", {"context": text, "asset": binary}, root / "run-v1")
        destination = Path(contract["destination_root"])
        destination.mkdir()
        for row in contract["files"]:
            shutil.copyfile(row["source_path"], destination / row["target_name"])
        received = verify_files(contract)
        if not (received["files_verified"] and received["source_versions_current"]):
            raise ValueError("normal_transfer_demo_failed")
        text.write_text("Task version: 2\n", encoding="utf-8")
        advanced = verify_files(contract)
        if not (advanced["files_verified"] and not advanced["source_versions_current"]):
            raise ValueError("source_update_demo_failed")
        (destination / "asset.snapshot").write_bytes(b"corrupted")
        rejected = verify_files(contract)
        if rejected["files_verified"]:
            raise ValueError("corruption_demo_failed")
        return {"scope": "local_fixture_only", "normal_transfer": received,
                "source_advanced": advanced, "corrupt_target": rejected,
                "native_memory_verified": False, "network_transport_tested": False}


if __name__ == "__main__":
    print(json.dumps(demo(), ensure_ascii=False, indent=2))
