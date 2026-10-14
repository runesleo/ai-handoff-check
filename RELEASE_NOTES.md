# AI Handoff Check v0.1.0

> “Your other AI said done. Was it using the latest file?”

The first open-source release of AI Handoff Check is a standalone Agent Skill plus standard-library Python verifier. It checks three distinct things: file integrity, source freshness, and the need for a separate task-output assertion.

**Start with the [20-second visual walkthrough](demo/index.html) and [README example](README.md).**

## Included

- A copyable Agent Skill (`SKILL.md`) with a provider-neutral, bounded handoff workflow.
- A local `prepare` → existing approved transport → `verify` process.
- A pinned SHA-256 manifest, version drift detection and strict structured receipt checking.
- Clear rejection of damaged files, symlinks/hardlinks masquerading as copies and FIFO manifest paths.
- A read-only `doctor --json` and synthetic offline `demo`.
- English and Chinese documentation, an illustrated SVG, and a three-stage interactive HTML explanation.
- MIT license, independent reviewer findings and regression tests.

## Validation

- 21 standalone tests passed on the release candidate.
- Clean temporary HOME and Python `-I -B` process test passed: doctor, demo and tests in 1.85 seconds.
- Static privacy preflight passed; no private source lists, tokens, paid transport or provider credentials packaged.
- Underlying owner workflow had two real nonsensitive controller-to-Bot file handoffs with a version update. This distributable does **not** claim general cross-provider interoperability.

## What this is not

It is not an automatic ChatGPT/Claude/Grok file mover, universal memory sync, wallet or credential agent, background scheduler, or exactly-once network transport. The three-step interactive UI is a **simulation**, not an account-connected live demo. A successful file hash does not prove semantic adoption by a model.

## Get started

```sh
python3 -B scripts/handoff.py doctor --json
python3 -B scripts/handoff.py demo
```

Read [install.md](install.md) to connect the Skill to your existing AI workflow. Report reproducible installation issues in GitHub Issues, but never upload manifests containing private paths, passwords, session files or chat histories.
