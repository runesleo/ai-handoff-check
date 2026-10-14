# Independent code review — v0.1.0 public preview

Scope: the standalone distributable Skill, CLI, protocol, demo and tests. The reviewer used read-only tools. The review is not an external provider interoperability certification.

## Blockers found and repaired

- **Hardlink masquerading as a copied file** — Receiver verification previously checked whether a target shared an inode with its sealed snapshot, but did not reject a hardlink to an original input or a third file. The verifier now requires an independent regular destination file with exactly one hardlink; two specific regression cases cover this.
- **Blocking manifest input** — Opening a FIFO manifest could wait indefinitely before its content was validated. The CLI now opens manifest inputs nonblocking with no-follow protection and confirms the opened descriptor is a bounded regular file. A FIFO regression requires prompt JSON failure with exit code 2.

## Post-fix checks

- 21 isolated tests passed with synthetic files, including two checks for the illustrated README and offline three-step walkthrough. The independent code review focused on the earlier 14-test candidate; these two additional presentation tests were added afterward.
- Offline demo passed: correct byte delivery, changed source detection, corrupted destination rejection.
- Public repository privacy and release preflight returned exit code 0.
- No private source maps, account credentials, scheduler or provider transport are included in the distribution.

## Final independent review: 2 P2 findings, 0 P0/P1

An additional independent Codex read-only review of the visually redesigned release candidate reported two P2 issues:

1. **Circular source symlinks can raise RuntimeError on Python 3.10/3.11.** Fixed in the verifier's current-source check and the CLI's JSON failure boundary. Added two regression tests (a simulated circular-origin check and a structured prepare error).
2. **The illustrated v1/v2 filenames implied automatic adjacent-file discovery.** The actual verifier tracks one pinned input path and its content. Updated the README (both languages), SVG, interactive HTML and presentation tests to consistently show one `brief.md` source path with content versions v1→v2.

After these changes, **21 tests passed**, the offline example succeeded under Python `-I -B`, and clean temporary-HOME first success passed. The reviewer did not run write-producing tests; these post-fix results were verified by the implementation/testing workflow rather than a claimed second reviewer approval.

No P0/P1 blockers were reported. The separate first review had already caught and resolved hardlink and FIFO concerns.

## Limitations

The tested artifact is a local file-verification Skill. A real transfer needs an existing authorized transport and independent destination access. No claim is made for native-memory adoption, arbitrary remote adapters, exactly-once delivery, or protection from a malicious concurrent filesystem writer.
