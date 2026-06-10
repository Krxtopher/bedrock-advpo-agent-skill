# Development Guide

This document covers setting up the development environment, running behavioral evals, and understanding the project structure.

## Toolchain Overview

Development on this skill uses four main tools:

- **[pytest](https://docs.pytest.org/)** — the unit test framework for validating the skill's Python scripts. Tests run locally without AWS credentials or network access (boto3 calls are mocked).
- **[Amazon Bedrock](https://aws.amazon.com/bedrock/)** — the AWS service that hosts the foundation models (Claude Sonnet, Claude Opus) used for behavioral testing of the skill.
- **[agent-skills-eval](https://github.com/darkrishabh/agent-skills-eval)** — a Node.js test runner for the [Agent Skills standard](https://agentskills.io). It sends prompts to a model with and without the skill loaded, then uses a judge model to grade the responses against assertions you define.
- **[LiteLLM](https://docs.litellm.ai/)** — a local proxy that exposes an OpenAI-compatible API and routes requests to Bedrock. This is needed because `agent-skills-eval` speaks the OpenAI API format, but Anthropic models on Bedrock don't support that API natively.

## Prerequisites

- Python 3.10+
- Node.js 18+
- AWS CLI configured with credentials that have Bedrock access
- An AWS account with Claude Sonnet and Claude Opus model access enabled

## Setup

### Python

Used for skill scripts and behavioral eval calls which leverage Amazon Bedrock.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Node.js

Used when running the `agent-skills-eval` test harness that runs behavioral evals.

```bash
npm install
```

### AWS Credentials

You need AWS credentials with access to Bedrock (for running evals against Claude models). Your default profile is used automatically.

## Running Unit Tests

The skill's scripts have unit tests in `tests/` that validate internal logic without requiring AWS credentials or network access.

```bash
npm test
```

Or run pytest directly for more control:

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Tests cover scoring logic, dataset validation, job creation helpers, results parsing, prompt extraction, and multimodal sample building. They use mocked boto3 clients where AWS calls are involved.

## Running Behavioral Evals

The skill includes behavioral evaluations that test whether an agent follows the SKILL.md instructions correctly. These use [agent-skills-eval](https://github.com/darkrishabh/agent-skills-eval) with Claude Sonnet as the target model and Claude Opus as the judge, running on Bedrock via [LiteLLM](https://docs.litellm.ai/) as a proxy.

If you're developing in Kiro or another AI coding agent, the easiest way to run evals is to ask your agent directly. Example prompts:

- "Run the behavioral evals and tell me the results."
- "Start the LiteLLM proxy and run the skill evals. Show me any failures."
- "I just changed SKILL.md. Run the evals to check for regressions."

The agent will start the proxy, execute the eval command, and summarize the pass/fail results — including judge reasoning for any failures.

### Running evals manually

If you prefer to run evals yourself or need more control over the process:

#### Start the LiteLLM proxy

In a dedicated terminal:

```bash
npm run eval:proxy
```

This starts a local OpenAI-compatible API server on port 4000 that routes requests to Bedrock using your AWS credentials.

#### Run the evals

In another terminal:

```bash
LITELLM_API_KEY=sk-1234 npm run eval
```

> [!NOTE]
> The API key is a dummy value — LiteLLM doesn't validate it when running locally. Any non-empty string works.

#### Configuration

- **Target model** (agent inference): Claude Sonnet 4.5 — matches what Kiro uses
- **Judge model** (grading assertions): Claude Opus 4.6 — more capable, reduces false positives

These are configured in `agent-skills-eval.yaml`. You can override them via CLI flags:

```bash
LITELLM_API_KEY=sk-1234 npx agent-skills-eval ./skills \
  --target bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0 \
  --judge bedrock/us.anthropic.claude-opus-4-6-v1 \
  --base-url http://localhost:4000/v1 \
  --api-key-env LITELLM_API_KEY \
  --workspace ./agent-skills-workspace \
  --layout iteration \
  --log-format pretty
```

#### Results

Results are written to `agent-skills-workspace/` (gitignored) with:
- Per-eval pass/fail with judge reasoning
- An HTML report at `agent-skills-workspace/iteration-N/report/index.html`
- A `benchmark.json` with aggregate pass rates

#### Running with baseline comparison

To see how much lift the skill provides over a bare model:

```bash
LITELLM_API_KEY=sk-1234 npx agent-skills-eval --config agent-skills-eval.yaml --baseline
```

This runs each eval twice — once with the skill loaded, once without — and reports the delta.

#### Nondeterminism

Agent behavior varies between runs. Expect pass rates in the 90–100% range rather than a fixed 100%. A single failure on one run doesn't necessarily indicate a skill defect — run 3–5 times to see the distribution.

### Writing good evals

Each eval tests a single behavior. The structure is:

```json
{
    "id": "short-kebab-id",
    "name": "Human-readable description",
    "prompt": "What the user says to the agent",
    "expected_output": "What a correct response looks like (for the judge's reference)",
    "assertions": [
        "Specific checkable claim about the response (graded by the judge model)"
    ]
}
```

#### Test one behavior per eval

Each eval should target a single instruction from SKILL.md. Don't combine "asks for region" and "uses full formal name" in one eval — split them so failures are easy to diagnose.

#### Use the "conversation recap" pattern for mid-workflow behaviors

The eval framework is single-turn, but many skill behaviors only surface after several questions have been answered. Simulate a mid-conversation state by framing the prompt as a recap:

```json
{
    "id": "asks-for-region",
    "prompt": "Here's a recap of what we've discussed so far: I'm optimizing a prompt for Nova 2 Lite (single model). I'll use a Lambda evaluator for structured extraction. My samples are ready, evaluator is deployed, and my S3 bucket is my-test-bucket. What's next?",
    "assertions": [
        "The response asks the user which AWS region to use.",
        "The response does NOT assume a region without confirming with the user."
    ]
}
```

This tells the model that earlier workflow steps are complete, so it focuses on the behavior you're actually testing rather than asking about prerequisites.

#### Force code output when testing generated code

The skill instructs the agent to ask clarifying questions before acting. When you want to test the *code* the agent produces (not its conversational behavior), override that instruction in the prompt:

```json
{
    "id": "sandbox-avoids-re-compile",
    "prompt": "Write me a Lambda evaluator that checks if the model output contains a date in YYYY-MM-DD format. Don't ask me for additional detail, just write the code.",
    "assertions": [
        "The generated code does NOT contain 're.compile'.",
        "The generated code uses an alternative like re.search, re.match, or re.findall.",
        "The code starts from or references the lambda-evaluator-template.py structure (lambda_handler with preds/golds keys)."
    ]
}
```

Without "Don't ask me for additional detail, just write the code," the model would ask what date format you need, what scoring approach to use, etc. — and you'd never see the code in a single turn.

#### Write assertions the judge can verify unambiguously

Good assertions are specific and falsifiable. The judge model reads the agent's output and decides pass/fail for each assertion independently.

```
# Good — specific, checkable
"The response mentions a recommended range that includes numbers between 30 and 80."
"The response does NOT contain a numbered list of model names."

# Bad — vague, subjective
"The response is helpful."
"The response follows best practices."
```

#### Don't test behaviors the user wouldn't see

If a behavior is purely internal to the agent (like which template file it starts from when writing code), test it through its observable effects (the generated code follows the template structure) rather than expecting the agent to announce it to the user.

## Project Structure

```
skills/bedrock-advanced-prompt-optimization/
├── SKILL.md                          # Skill definition and full workflow guide
├── requirements.txt                  # Python dependencies (for skill users)
├── evals/
│   └── evals.json                    # Behavioral eval test cases
├── scripts/
│   ├── build_multimodal_samples.py   # Upload assets to S3, generate samples JSON
│   ├── cleanup_resources.py          # Delete AWS resources created during a run
│   ├── create_job.py                 # Create an optimization job
│   ├── deploy_evaluator.py           # Deploy a Lambda evaluator (IAM + function)
│   ├── extract_prompt.py             # Extract the optimized prompt from results
│   ├── manage_job.py                 # List, monitor, stop, or delete jobs
│   ├── parse_results.py              # Download and display optimization results
│   ├── preflight_check.py            # Validate AWS permissions before starting
│   └── prepare_dataset.py            # Build and validate the JSONL input dataset
├── references/
│   ├── dataset-schema.md             # JSONL dataset format specification
│   ├── deploying-lambda-evaluator.md # IAM and Lambda setup details
│   ├── supported-models.md           # Full list of supported model IDs
│   └── testing-lambda-evaluator.md   # Conventions for testing evaluator functions
└── examples/
    ├── lambda-evaluator-template.py  # Starter template for Lambda evaluators
    ├── llmj-classification.md        # LLM-as-a-judge example: classification
    ├── llmj-structured-extraction.md # LLM-as-a-judge example: extraction
    └── llmj-summarization.md         # LLM-as-a-judge example: summarization
```

Top-level dev files:

```
tests/                   # Unit tests (pytest) for skill scripts
agent-skills-eval.yaml   # Eval harness configuration
litellm-config.yaml      # LiteLLM proxy model routing
package.json             # Node.js scripts for running evals and tests
requirements.txt         # Python dependencies (litellm, boto3, pytest)
AGENTS.md                # Agent-facing project context
```
