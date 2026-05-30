# Bedrock Advanced Prompt Optimization Agent Skill

## Project Structure

```
skills/bedrock-advanced-prompt-optimization/  — The canonical skill source (installed via `npx skills add`)
agent-skills-eval.yaml  — Behavioral eval configuration
litellm-config.yaml     — LiteLLM proxy model routing for evals
```

## Dependencies

- Python 3.10+
- Node.js 18+
- boto3 >= 1.35.0
- litellm[proxy] >= 1.86.0
- agent-skills-eval (npm)
- AWS CLI

## Running Behavioral Evals

1. Start the LiteLLM proxy: `npm run eval:proxy`
2. In a separate terminal: `LITELLM_API_KEY=sk-1234 npm run eval`

Results land in `agent-skills-workspace/` with an HTML report. Target model is Claude Sonnet 4.5, judge is Claude Opus 4.6.

## Key Conventions

- The abbreviation "AdvPO" is never used — always write "Advanced Prompt Optimization" or use contextual alternatives like "the optimizer" or "the service"
- S3 prefixes follow the pattern `prompt-optimization/{job-name}/`
- Resource tracking file is `prompt-optimization/resources.json`
- Eval test cases live in `skills/bedrock-advanced-prompt-optimization/evals/evals.json`
