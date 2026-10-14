# AI Handoff Check

[中文说明](README.zh.md) · [Agent install guide](install.md) · [MIT License](LICENSE) · [CI tests](https://github.com/runesleo/ai-handoff-check/actions/workflows/ci.yml)

**Your other AI said “done.” Was it working from the latest file?**

![Two AIs using different file versions; the check catches an outdated handoff](assets/handoff-flow.svg)

### See the problem in 20 seconds

**ChatGPT** creates `brief.md` with content version **v1**. You hand that file to **Grok (or another AI)** using a tool you already have. Later you edit the **same source path**, `brief.md`, to content version **v2**, but the other AI still holds the captured v1 bytes. The checker does not discover an adjacent newly named file automatically.

| Independent question | What the check says |
|---|---|
| Did the captured v1 file arrive intact? | **Yes** — its bytes match. |
| Is the receiving AI holding the latest source? | **No** — source v2, received v1. |
| Did it produce the right work? | **Not proven** — requires a separate output assertion. |

The old handoff was *correctly delivered*, but is now *outdated*. That difference is exactly what this Skill detects.

**[Explore the three-step interactive walkthrough](demo/index.html)** — download the repository and open `demo/index.html` locally in a browser. The page is a labeled illustration, not a real transfer.


## Install with your AI

Copy this instruction into your coding agent:

> Set up **AI Handoff Check** by following the official [install.md](https://github.com/runesleo/ai-handoff-check/blob/main/install.md). Start with the read-only doctor check. Don't authorize any remote file movement or change security settings.

A CLI-only user can clone the repository and run the same doctor and offline demo; no provider login is required. The illustrated three-step walkthrough is at [demo/index.html](demo/index.html).

## Try it in one minute

Requires Python 3.10+ on macOS/Linux. No pip install, credentials, network or API key:

```sh
python3 scripts/handoff.py demo
```

You'll see three deliberately different states: `FILES_VERIFIED_MEMORY_UNVERIFIED`, `FILES_VERIFIED_SOURCE_ADVANCED_MEMORY_UNVERIFIED`, and `FILES_NOT_VERIFIED` for a damaged destination.

For the actual Agent Skill, copy this whole folder to your agent's supported skills directory (see [install.md](install.md)). Then ask:

> Check my handoff to another AI. Use my existing transfer, verify which file version arrived, and independently test the work. Don't resend an uncertain task.

## How it works

1. **Freeze the input** with `prepare`, producing a controller-owned file manifest and SHA-256 digest in the existing task evidence directory.
2. **Hand off through your existing authorized tool.** This package does not upload or move files between accounts.
3. **Verify the received bytes and source freshness** with `verify` using the digest saved before sending.
4. **Test the output separately.** A byte-perfect copy cannot certify that an AI understood or used the details correctly.

```sh
python3 scripts/handoff.py prepare --run-id example-1 --run-root ./evidence/example-1 --source context=./context.md
# Send via your existing tool; save the digest returned above in your original trusted task record.
python3 scripts/handoff.py verify --manifest ./evidence/example-1/manifest.json --expect-sha256 "$PINNED_MANIFEST_SHA256" --require-current
```

The digest must come from the controller's trusted record, **not** from the receiving AI's reply. Unknown send outcome? Reconcile the existing run before any resend.

## What is tested, and what isn't

The underlying private workflow previously passed two real nonsensitive controller-to-Bot file handoffs, including a source-version change and an independently checked sample output. **This distributable Skill** has 21 local tests and an offline synthetic demo; it has **not** been certified on all providers.

It does **not** offer one-click ChatGPT-to-Grok transport, cloud mounts, continuous sync, native AI memory migration, task scheduling or guaranteed exactly-once delivery. One run supports 1–16 local files, each up to 32 MiB. Files and receipts can contain sensitive paths: keep them in your own task storage, not public bug reports.

## Feedback and next steps

If you actually install this and use it on your own files, open an Issue describing the host AI, whether your first handoff passed, and what confused you. **Do not attach raw manifests or private files.** Stars are appreciated, but a real first-success report helps improve the Skill more.

Possible next steps, **only if users need them**: additional provider-neutral example adapters, stronger workflow receipts, and clearer self-checks. No hosted SaaS is promised.

## About the author

Built by [Leo](https://x.com/runes_leo), an independent AI workflow builder. More experiments at [leolabs.me](https://leolabs.me).

## Development and license

```sh
python3 -B -m unittest discover -s tests -q
```

See [clean-environment first success](docs/FIRST_SUCCESS.md), [the protocol and trust boundary](references/protocol.md), [independent review](REVIEW-codex-pass.md), and [CHANGELOG](CHANGELOG.md). Licensed under [MIT](LICENSE). Remote transfer adapters and a hosted product are not included.
