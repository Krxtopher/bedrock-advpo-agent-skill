# Development Guide

This document covers setting up the development environment, running behavioral evals, and understanding the project structure.

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
agent-skills-eval.yaml   # Eval harness configuration
litellm-config.yaml      # LiteLLM proxy model routing
package.json             # Node.js scripts for running evals
requirements.txt         # Python dependencies (litellm, boto3)
AGENTS.md                # Agent-facing project context
```

## Setup

### Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Node.js

```bash
npm install
```

### AWS Credentials

You need AWS credentials with access to Bedrock (for running evals against Claude models). The default profile is used automatically.

## Running Behavioral Evals

The skill includes behavioral evaluations that test whether an agent follows the SKILL.md instructions correctly. These use [agent-skills-eval](https://github.com/darkrishabh/agent-skills-eval) with Claude Sonnet as the target model and Claude Opus as the judge, running on Bedrock via [LiteLLM](https://docs.litellm.ai/) as a proxy.

### Start the LiteLLM proxy

In a dedicated terminal:

```bash
npm run eval:proxy
```

This starts a local OpenAI-compatible API server on port 4000 that routes requests to Bedrock using your AWS credentials.

### Run the evals

In another terminal:

```bash
LITELLM_API_KEY=sk-1234 npm run eval
```

> [!NOTE]
> The API key is a dummy value — LiteLLM doesn't validate it when running locally. Any non-empty string works.

### Configuration

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

### Results

Results are written to `agent-skills-workspace/` (gitignored) with:
- Per-eval pass/fail with judge reasoning
- An HTML report at `agent-skills-workspace/iteration-N/report/index.html`
- A `benchmark.json` with aggregate pass rates

### Adding new evals

Add test cases to `skills/bedrock-advanced-prompt-optimization/evals/evals.json`. Each eval needs:

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

Tips:
- Test one behavior per eval
- Use the "conversation recap" pattern for behaviors that occur later in the workflow
- Add "Don't ask me for additional detail, just write the code." when testing code output
- Keep assertions specific and falsifiable — vague assertions produce inconsistent grading

### Nondeterminism

Agent behavior varies between runs. Expect pass rates in the 90–100% range rather than a fixed 100%. A single failure on one run doesn't necessarily indicate a skill defect — run 3–5 times to see the distribution.

## Running with Baseline Comparison

To see how much lift the skill provides over a bare model:

```bash
LITELLM_API_KEY=sk-1234 npx agent-skills-eval --config agent-skills-eval.yaml --baseline
```

This runs each eval twice — once with the skill loaded, once without — and reports the delta.
