# Bedrock Advanced Prompt Optimization Agent Skill

An agent skill for [Kiro IDE](https://kiro.dev) that lets AI coding agents create, manage, and analyze [Amazon Bedrock Advanced Prompt Optimization](https://docs.aws.amazon.com/bedrock/latest/userguide/advanced-prompts.html) jobs through a guided conversational workflow.

## What It Does

Advanced Prompt Optimization takes your prompt templates, evaluation samples, and a scoring method, then runs iterative inference → evaluate → rewrite loops. The result is an optimized prompt tailored to a specific model (or a comparison across multiple models).

This skill packages the entire workflow — dataset preparation, evaluator deployment, job creation, monitoring, and result extraction — into scripts that an AI agent orchestrates on your behalf.

## Compatibility

Compatible with any coding agent that supports the [Agent Skills standard](https://agentskills.io). Tested with Amazon Kiro IDE and Claude Code. Requires Python 3.10+, boto3, and AWS CLI.

## Installation

Install the skill to your agent using the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add --agent kiro-cli https://github.com/Krxtopher/bedrock-advpo-agent-skill
```

Or from a local clone:

```bash
npx skills add --agent kiro-cli ./bedrock-advpo-agent-skill
```

> [!TIP]
> Replace `kiro-cli` with the agent value appropriate for your setup (e.g. `claude-code`, `codex`, etc.). Run `npx skills add --help` to see available options.

Then install Python dependencies:

```bash
pip install -r skills/bedrock-advanced-prompt-optimization/requirements.txt
```

## Prerequisites

- Python 3.10+
- AWS CLI configured with credentials that have access to Bedrock, S3, Lambda, and IAM
- boto3 >= 1.35.0

## Project Structure

```
skills/bedrock-advanced-prompt-optimization/
├── SKILL.md                          # Skill definition and full workflow guide
├── requirements.txt                  # Python dependencies
├── scripts/
│   ├── build_samples.py              # Upload assets to S3, generate samples JSON
│   ├── cleanup_resources.py          # Delete AWS resources created during a run
│   ├── create_job.py                 # Create an Advanced Prompt Optimization optimization job
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

## Workflow Overview

The skill guides you through these steps:

1. **Clarify goal** — single-model optimization or multi-model comparison
2. **Select target model(s)** — any text-generation model available in Bedrock
3. **Choose evaluation method** — Lambda evaluator, LLM-as-a-judge, steering criteria, or system default
4. **Design evaluator metrics** — if using a Lambda evaluator, define scoring logic
5. **Build samples** — upload documents/images to S3 and generate sample metadata
6. **Prepare dataset** — validate and format the JSONL input file
7. **Upload to S3** — place the dataset in the correct region
8. **Create job** — launch the optimization with pre-flight model access checks
9. **Monitor** — poll job status until completion
10. **Parse results** — download and display score improvements
11. **Extract prompt** — save the optimized prompt as a ready-to-use file

## Usage

In Kiro IDE, activate the skill by mentioning prompt optimization, Advanced Prompt Optimization, or related topics in a vibe session. The agent will walk you through the workflow interactively, asking one question at a time.

For other compatible agents, point them at the `SKILL.md` file for the full workflow instructions.

## Running Behavioral Evals

The skill includes behavioral evaluations that test whether an agent follows the SKILL.md instructions correctly. These use [agent-skills-eval](https://github.com/darkrishabh/agent-skills-eval) with Claude Sonnet on Bedrock via [LiteLLM](https://docs.litellm.ai/) as a proxy.

### Prerequisites

1. AWS credentials configured (default profile with Bedrock access)
2. LiteLLM installed: `pip install litellm[proxy]`
3. Node.js dependencies: `npm install`

### Running

In one terminal, start the LiteLLM proxy:

```bash
npm run eval:proxy
```

In another terminal, run the evals:

```bash
LITELLM_API_KEY=sk-1234 npm run eval
```

(LiteLLM requires an API key but doesn't validate it when running locally — any value works.)

Results are written to `agent-skills-workspace/` with an HTML report.

## License

Internal use.
