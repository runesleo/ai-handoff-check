# Install AI Handoff Check — instructions for coding agents

This is a local, offline-verifiable Agent Skill, **not** a cross-provider file transfer service. Follow the steps in order; if blocked, report the issue rather than changing permissions, networking or credentials.

## 1. Read-only check (before any install)

Requirements: Python 3.10+, macOS/Linux, standard library only. From an extracted/checked-out folder:

```sh
python3 -B scripts/handoff.py doctor --json
```

Only `OK` means the complete local directory is present. `MISSING` or `BLOCKED` is a stop, with the next step and owner given in JSON. No remote account is contacted.

## 2. Obtain the Skill

Official source: https://github.com/runesleo/ai-handoff-check

```sh
git clone https://github.com/runesleo/ai-handoff-check.git
cd ai-handoff-check
python3 -B scripts/handoff.py doctor --json
```

Alternatively, download the release ZIP from the GitHub Releases page, extract the `ai-handoff-check` folder, and enter it. Never execute installation scripts from unknown mirrors.

## 3. Install in an agent that supports Skills

Use the target application's documented Skills directory. A cross-agent option is `~/.agents/skills/`; for other hosts consult their own Skills directory documentation. Copy **the entire directory** named `ai-handoff-check`, preserving `SKILL.md`, `scripts/`, `references/`, `demo/` and `assets/`.

**Do not overwrite an existing Skill of the same name.** Inspect it and obtain user approval before changing anything. No automatic installer is included.

For agents without Skills support, keep the folder anywhere and ask the agent to read `SKILL.md`; then call the CLI with its full path.

## 4. First successful run

Run this safe synthetic example from the checked-out directory:

```sh
python3 -B scripts/handoff.py demo
python3 -B -m unittest discover -s tests -q
```

Expected: a completed example with file integrity `true`, an advanced source identified as stale, a corrupt destination rejected, and `native_memory_verified: false`. No real file transfer is performed.

To ask your agent:

> Read AI Handoff Check. I have an existing authorized tool for delivering task files to another AI. Pin the file version, let the existing tool deliver it, then independently verify actual destination bytes and source freshness. Stop on unknown outcomes rather than resending.

## 5. Boundaries and user-only actions

- User approval is required before handling private files, expanding a destination path, or connecting any external account.
- Do not request API keys, cookies, wallet data or passwords.
- `prepare` creates local bounded snapshots; `verify` reads local accessible files. They do **not** send data to other AI providers.
- Save the manifest SHA-256 in the original trusted task record, not from the receiving AI's reply.
- Do not interpret verified bytes as verified native AI memory or correct semantic output.
- Unknown send outcome: reconcile the original task first; do not blindly retry.

## 6. Finish

Run `python3 -B scripts/handoff.py doctor --json` again and report which checks are `OK` and what remains unverified. Install success is not proof that a remote receiving AI has been accessed.
