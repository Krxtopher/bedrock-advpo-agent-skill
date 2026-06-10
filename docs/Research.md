The following is a list of resources that informed the development of this skill.

## Eval Concepts & Methodology

[Practical Guide to Evaluating and Testing Agent Skills (Phil Schmid)](https://www.philschmid.de/testing-skills)

[Demystifying evals for AI agents (Anthropic)](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

[Improving Skill-Creator: Test, Measure, and Refine Agent Skills (Anthropic/Claude Blog)](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills)

## Eval Tooling

### agent-skills-eval (currently in use)

- **Repo:** https://github.com/darkrishabh/agent-skills-eval
- **npm:** https://www.npmjs.com/package/agent-skills-eval
- **Author:** Rishabh Mehan (darkrishabh), California
- **What it does:** A test runner for agentskills.io-style skills. Uses a LiteLLM proxy to call LLM APIs directly, with LLM-as-judge grading. Does not run against real agent CLIs.
- **Stars:** ~553

### Skillgrade (potential alternative for real-agent evals)

- **Repo:** https://github.com/mgechev/skillgrade
- **npm:** `skillgrade` (install globally)
- **Author:** Minko Gechev (mgechev)
- **Blog post:** https://blog.mgechev.com/2026/02/26/skill-eval/
- **What it does:** Runs skills against real coding agent CLIs (Claude Code, Gemini CLI, Codex, OpenCode, and any ACP-compatible agent including Kiro) in Docker containers. Each trial gets a fresh environment. Supports deterministic graders (shell scripts) and LLM rubric graders. The agent discovers skills naturally via standard paths rather than having them injected.
- **Kiro support:** Via ACP protocol — Kiro CLI supports `kiro-cli acp` mode, and skillgrade supports `--agent=acp --acp-command="kiro-cli --acp"`
- **Claude Code support:** Native `--agent=claude` flag
- **Stars:** ~502
- **Why it's interesting:** More realistic than agent-skills-eval because the agent discovers and loads the skill the same way it would in production. Better for testing how the skill actually performs in Claude Code and Kiro rather than against a raw LLM API.