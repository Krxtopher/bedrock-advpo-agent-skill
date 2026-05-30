# Bedrock Advanced Prompt Optimization Agent Skill

An agent skill for [Kiro IDE](https://kiro.dev) that lets AI coding agents create, manage, and analyze [Amazon Bedrock Advanced Prompt Optimization](https://docs.aws.amazon.com/bedrock/latest/userguide/advanced-prompts.html) jobs through a guided conversational workflow.

## What It Does

Advanced Prompt Optimization takes your prompt templates, evaluation samples, and a scoring method, then runs iterative inference → evaluate → rewrite loops. The result is an optimized prompt tailored to a specific model (or a comparison across multiple models).

This skill packages the entire workflow — dataset preparation, evaluator deployment, job creation, monitoring, and result extraction — into scripts that an AI agent orchestrates on your behalf.

## Installation

Install the skill to your agent using the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add --agent kiro-cli https://github.com/Krxtopher/bedrock-advpo-agent-skill
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

## Compatibility

Compatible with any coding agent that supports the [Agent Skills standard](https://agentskills.io). Tested with Amazon Kiro IDE and Claude Code.

## How It Works

The skill guides your agent through these steps interactively, asking one question at a time:

1. **Clarify goal** — single-model optimization or multi-model comparison
2. **Select target model(s)** — any text-generation model available in Bedrock
3. **Choose evaluation method** — Lambda evaluator, LLM-as-a-judge, steering criteria, or system default
4. **Design evaluator metrics** — if using a Lambda evaluator, define scoring logic
5. **Build samples** — create evaluation data from your documents or text inputs
6. **Prepare dataset** — validate and format the JSONL input file
7. **Upload to S3** — place the dataset in the correct region
8. **Create job** — launch the optimization with pre-flight checks
9. **Monitor** — poll job status until completion
10. **Parse results** — download and display score improvements
11. **Extract prompt** — save the optimized prompt as a ready-to-use file

## Usage

In Kiro IDE, activate the skill by mentioning prompt optimization or related topics in a vibe session. The agent will walk you through the workflow interactively.

For other compatible agents, point them at the `SKILL.md` file for the full workflow instructions.

## License

This project is licensed under the [MIT License](LICENSE).

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for setup instructions, running unit tests, and running behavioral evals.
