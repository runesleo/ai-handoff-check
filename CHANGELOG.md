# Changelog

All notable changes to this public package will be recorded here.

## [0.1.0] — 2026-10-14

### Added
- AI Handoff Check Agent Skill, offline `prepare`/`verify` workflow and strict structured receipts.
- Read-only `doctor --json` with explicit `OK` and `MISSING` status.
- Source-version drift detection, tamper/missing-file rejection, and pinned manifest SHA-256.
- GitHub-ready SVG explanation and offline three-step interactive HTML demonstration.
- Independent security review, bilingual documentation, install guidance and clean-environment receipt.
- Standard-library tests on synthetic source/destination files.

### Fixed before first release
- Reject hardlinks and symlinks used to impersonate independently copied files.
- Reject nonregular/FIFO manifests without a blocking read.
- Support Python isolated `-I` execution from a different working directory.

### Known limits
- Uses the user's existing authorized file transport.
- Does not synchronize native AI memory, validate arbitrary model outputs, or schedule/retry remote jobs.
- Each run has 1–16 files, with a maximum 32 MiB per file.
