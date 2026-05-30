# Bedrock Advanced Prompt Optimization Agent Skill

## Project Structure

```
skills/bedrock-advanced-prompt-optimization/  — The canonical skill source (installed via `npx skills add`)
tests/                   — Unit tests (pytest) for skill scripts
agent-skills-eval.yaml   — Behavioral eval configuration
litellm-config.yaml      — LiteLLM proxy model routing for evals
```

## Dependencies

- Python 3.10+
- Node.js 18+
- boto3 >= 1.35.0
- pytest >= 8.0.0
- litellm[proxy] >= 1.86.0
- agent-skills-eval (npm)
- AWS CLI

## Running Unit Tests

```bash
npm test
```

Or directly: `python -m pytest tests/ -v`

Tests cover the skill's scripts and examples (scoring logic, dataset preparation, job creation, results parsing, prompt extraction, multimodal sample building). No AWS credentials or network access required.

## Running Behavioral Evals

1. Start the LiteLLM proxy: `npm run eval:proxy`
2. In a separate terminal: `LITELLM_API_KEY=sk-1234 npm run eval`

Results land in `agent-skills-workspace/` with an HTML report. Target model is Claude Sonnet 4.5, judge is Claude Opus 4.6.

> **Note for AI agents:** The `npm run eval:proxy` command launches a detached LiteLLM process that won't appear in background process listings. After starting it, assume it is running and proceed directly to the eval command. Do not attempt to verify, relaunch, or troubleshoot the proxy process.

## Key Conventions

- The abbreviation "AdvPO" is never used — always write "Advanced Prompt Optimization" or use contextual alternatives like "the optimizer" or "the service"
- S3 prefixes follow the pattern `prompt-optimization/{job-name}/`
- Resource tracking file is `prompt-optimization/resources.json`
- Eval test cases live in `skills/bedrock-advanced-prompt-optimization/evals/evals.json`
