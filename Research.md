# Eval Framework Research

Research into lightweight eval frameworks for testing agent skills. This document
captures the options evaluated and the reasoning behind the direction chosen.

## Goal

Find a lightweight eval framework that supports:

1. **Headless agent execution** — run evals against **Claude Code headless** or the
   **Kiro CLI headless**, so the system under test (SUT) is a real tool-using agent,
   not just a raw model endpoint.
2. **Deterministic, Python-based evals** — exact checks expressed in Python.
3. **LLM-judge evals** — using a model on **Amazon Bedrock** as the judge.

## Headless Agent Hooks (Prerequisite)

Both candidate agents expose stable non-interactive entry points that an eval
harness can wrap. Each reads a prompt and writes its result to stdout.

| Agent | Invocation | Notes |
| --- | --- | --- |
| Kiro CLI | `kiro-cli chat --no-interactive --trust-tools=read,grep "prompt"` | Requires `KIRO_API_KEY`. Use `--trust-tools` (least privilege) or `--trust-all-tools`. ([docs](https://kiro.dev/docs/cli/headless/)) |
| Claude Code | `claude -p "prompt" --output-format json` | `-p`/`--print` for non-interactive; JSON output for structured parsing. ([docs](https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-headless)) |

> [!NOTE]
> This is the key differentiator from the project's current `agent-skills-eval`
> setup, which swaps the skill in/out against a *model* (via a LiteLLM proxy to
> Bedrock) and judges the raw model response. It never drives Kiro or Claude Code
> as a real agent with tools. Moving to a headless-agent harness is a capability
> upgrade, not just a tooling swap.

## Options Evaluated

### Inspect AI (chosen direction)

Open-source Python eval framework from the UK AI Security Institute and Meridian Labs.

- **Headless agent execution** — a [solver](https://inspect.aisi.org.uk/solvers.html)
  is arbitrary Python, so a custom solver can shell out to the agent CLI and capture
  stdout into the `TaskState`. Run with `--model none` since the SUT is the agent, not
  a model. Swapping Kiro for Claude Code is a one-line change in the solver.
- **Deterministic Python evals** — built-in scorers (`includes`, `match`, `pattern`,
  `exact`, `f1`) plus custom `@scorer` functions (`async def score(state, target) -> Score`)
  for arbitrary Python pass/fail or numeric logic.
- **LLM judge on Bedrock** — built-in `model_graded_qa()` / `model_graded_fact()`
  scorers. The judge model is bound via a `grader` model role to Inspect's
  [native Bedrock provider](https://inspect.aisi.org.uk/providers.html). For Claude on
  Bedrock, `anthropic/bedrock/...` uses standard AWS credentials directly — **no
  LiteLLM proxy required**.
- **Footprint** — heavier and more code-centric than alternatives, but fully
  Python-native (fits this repo's conventions) with a strong trace viewer.
- **Org alignment** — other teams in the org are standardizing on Inspect AI, which
  makes the investment more valuable.

Sketch of the architecture:

```
skill_evals.py
├── dataset   → eval cases (port from evals/evals.json)
├── solver    → custom: shell out to kiro-cli / claude headless, capture stdout
└── scorers   → custom @scorer (deterministic Python) + model_graded_qa (Bedrock judge)
```

Example judge invocation:

```bash
inspect eval skill_evals.py \
  --model none \
  --model-role grader=anthropic/bedrock/us.anthropic.claude-opus-4-6-v1
```

### promptfoo (strong lightweight alternative)

Open-source, config/YAML-driven eval and red-team tool (Node-based, with first-class
Python support).

- **Headless agent execution** — the
  [custom-script / `exec` provider](https://www.promptfoo.dev/docs/providers/custom-script)
  lets any shell command act as a provider, so the agent CLI's stdout becomes the
  output under test.
- **Deterministic Python evals** —
  [`python` assertions](https://promptfoo.dev/docs/configuration/expected-outputs/python)
  run a custom Python function returning pass/fail/score.
- **LLM judge on Bedrock** — native
  [AWS Bedrock provider](https://www.promptfoo.dev/docs/providers/aws-bedrock) plus
  [`llm-rubric`](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/);
  set the judge via `defaultTest.options.provider`. Talks to Bedrock directly — no
  LiteLLM proxy.
- **Footprint** — lightweight, fast to stand up, built-in HTML report. Closest in
  spirit to the current `agent-skills-eval` setup.

### Other tools considered

- **DeepEval** (confident-ai) — pytest-style LLM eval framework. Capable, but more
  oriented toward LLM-application output testing than driving an external agent CLI as
  the SUT.
- **Pydantic Evals** — clean deterministic + LLM-judge model, good ergonomics. Viable,
  but less momentum for headless-agent SUTs and no org standardization signal.
- **Amazon Bedrock (AgentCore) Evaluations / Model Evaluation** — managed LLM-as-a-judge
  plus code-based evaluators. Useful for Bedrock-hosted workloads, but a managed service
  rather than a lightweight local harness for driving an arbitrary agent CLI.

## Comparison

| Requirement | Inspect AI | promptfoo |
| --- | --- | --- |
| Headless agent CLI as SUT | Custom solver (Python) | Custom-script / `exec` provider |
| Deterministic Python evals | Built-in + custom `@scorer` | `python` assertions |
| Bedrock LLM judge | `model_graded_qa` + Bedrock provider | `llm-rubric` + Bedrock provider |
| LiteLLM proxy needed | No | No |
| Config style | Python-native | YAML-driven |
| Footprint | Heavier, more flexible | Lightweight |

## Decision

Both Inspect AI and promptfoo fully meet the three requirements, so this is not a
"no good options" situation. The direction chosen is **Inspect AI**, because:

- It is fully Python-native, matching this repo's conventions.
- It offers deeper agent/trace introspection.
- Other teams in the org are standardizing on it, making it a valuable skill to build.

## Sources

- [Kiro CLI — Headless mode](https://kiro.dev/docs/cli/headless/)
- [Claude Code — Headless mode](https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-headless)
- [Inspect AI — Solvers](https://inspect.aisi.org.uk/solvers.html)
- [Inspect AI — Scorers](https://inspect.aisi.org.uk/scorers.html)
- [Inspect AI — Model Providers](https://inspect.aisi.org.uk/providers.html)
- [promptfoo — Custom Scripts provider](https://www.promptfoo.dev/docs/providers/custom-script)
- [promptfoo — Python assertions](https://promptfoo.dev/docs/configuration/expected-outputs/python)
- [promptfoo — AWS Bedrock provider](https://www.promptfoo.dev/docs/providers/aws-bedrock)
- [promptfoo — LLM Rubric](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/)

> Content was rephrased for compliance with licensing restrictions.
