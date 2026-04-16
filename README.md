# vireo-scope-loop

An agentic discovery and validation loop that systematically identifies what spreadsheet workflows real finance professionals perform, determines whether a specific project called Vireo can handle them, and surfaces the gaps worth building — without the product becoming bloated or niche to one role.

This is a **meta-tool** that operates *on* Vireo. It is not part of the Vireo product and should never be a dependency of it.

## How it works

The loop runs a multi-phase pipeline powered by Claude (via the Anthropic API):

```
Scope agents ─── generate realistic Excel workflows per finance role
      │
Canonicalizer ── decompose into spreadsheet primitives and cluster
      │
Translator ───── extract precise input/output schemas per cluster
      │
Auditor ──────── check each cluster against the Vireo capability manifest
      │               PASS → loop restarts
      │               FAIL ↓
Frequency ────── track how often each gap surfaces across roles
      │
PM agent ─────── accept / reject / defer the gap
      │               REJECT → loop restarts
      │               DEFER  → defer queue
      │               ACCEPT ↓
Spec writer ──── write implementation spec → HUMAN REVIEW GATE
      │
Executor ─────── implement via Claude Code (planned)
      │
Reviewer ─────── test new feature + regression (planned)
```

**Key design decisions:**
- Gaps must surface 3+ times across 2+ distinct roles before escalating to the PM agent — single-occurrence niche gaps are filtered out.
- The PM agent rejects anything that would make Vireo more like an ERP or only serves one niche role. It accepts gaps that add composable primitives.
- No code is generated until a human approves the spec.

## Roles and ICP weighting

Scope agents generate workflows from the perspective of 7 finance roles, weighted by ICP priority:

| Role | Weight |
|------|--------|
| FP&A Analyst | 40% |
| FP&A Manager | 20% |
| Treasury Analyst | 10% |
| Credit Analyst | 10% |
| Project Finance Analyst | 10% |
| Corporate Development Associate | 5% |
| Controller | 5% |

## Project structure

```
vireo-scope-loop/
├── orchestrator.py              # Main loop — async, runs all phases
├── config.py                    # API keys, model selection, role weights
├── utils.py                     # Shared helpers (clean_json_response, etc.)
├── agents/
│   ├── base_agent.py            # BaseAgent — handles API calls, prompt caching
│   ├── scope_agents.py          # Role-parameterized workflow generation
│   ├── canonicalizer_agents.py  # Dedup + cluster into primitives
│   ├── translator_agents.py     # Extract input/output schemas
│   ├── auditor_agents.py        # Check against capability manifest
│   ├── pm_agents.py             # Accept / reject / defer gate
│   └── spec_writer_agents.py    # Write implementation specs
├── manifest/
│   └── vireo_manifest.json      # Vireo capabilities (committed, curated input)
├── state/                       # Runtime state (gitignored, regenerated)
│   ├── frequency_log.json
│   ├── defer_queue.json
│   └── regression_suite.json
├── output/                      # Generated spec files (gitignored)
└── requirements.txt
```

## Setup

**Prerequisites:** Python 3.12+

1. Clone the repo and create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate    # Windows PowerShell
   # or
   source .venv/bin/activate # macOS/Linux
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Store your Anthropic API key in the system keyring:
   ```python
   import keyring
   keyring.set_password("vireo-scope-loop", "vireo-scope-loop", "sk-ant-...")
   ```
   The key is retrieved at runtime via `keyring.get_password()` — it never appears in source.

## Usage

Run the full discovery loop:

```bash
python orchestrator.py
```

A single session will:
1. Generate ~350 workflows across all roles (7 roles x 5 iterations x ~10 workflows each)
2. Canonicalize them into clusters of shared spreadsheet primitives
3. Translate clusters into precise schemas
4. Audit against the Vireo capability manifest
5. Track gap frequencies and escalate those above threshold
6. Run escalated gaps through the PM gate
7. Write implementation specs for accepted gaps

Output is printed to the console via [Rich](https://github.com/Textualize/rich). Specs are written to `output/`.

## Models

- **Sonnet** (`claude-sonnet-4-5`): scope, canonicalizer, translator, spec writer
- **Opus** (`claude-opus-4-6`): auditor, PM agent (judgment-heavy decisions)

## Testing

```bash
pytest
```

Tests use `pytest` and `pytest-asyncio` for async agent tests.

## Manifest maintenance

After any feature ships in Vireo (whether from this loop or not), update `manifest/vireo_manifest.json`. The auditor evaluates against this manifest, so stale entries cause false gap reports.
