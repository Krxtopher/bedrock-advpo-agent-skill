"""Custom solver that drives Kiro CLI in headless mode as the system under test."""

import asyncio
import logging
from pathlib import Path

from inspect_ai.solver import Solver, TaskState, solver

logger = logging.getLogger(__name__)

# Path to the skill definition, relative to the repo root.
SKILL_MD_PATH = Path(__file__).parent.parent / "skills" / "bedrock-advanced-prompt-optimization" / "SKILL.md"


def _load_skill_context() -> str:
    """Load the SKILL.md content to inject as system context for the agent."""
    if SKILL_MD_PATH.exists():
        return SKILL_MD_PATH.read_text()
    logger.warning("SKILL.md not found at %s — running without skill context.", SKILL_MD_PATH)
    return ""


@solver
def kiro_cli_headless(
    trust_tools: str = "read,grep",
    timeout_seconds: int = 120,
) -> Solver:
    """Solver that invokes kiro-cli in headless mode and captures the response.

    The solver:
    1. Reads the SKILL.md content.
    2. Constructs a prompt that includes the skill as system context plus the
       eval sample's input.
    3. Shells out to `kiro-cli chat --no-interactive` and captures stdout.
    4. Writes the CLI output into the TaskState as the model completion.

    Args:
        trust_tools: Comma-separated tool categories to auto-approve.
        timeout_seconds: Max seconds to wait for the CLI to respond.
    """
    skill_context = _load_skill_context()

    async def solve(state: TaskState, generate) -> TaskState:
        # Build the full prompt: skill context + user input
        user_input = state.input_text
        full_prompt = (
            f"You have the following skill loaded:\n\n"
            f"<skill>\n{skill_context}\n</skill>\n\n"
            f"User request: {user_input}"
        )

        cmd = [
            "kiro-cli", "chat",
            "--no-interactive",
            f"--trust-tools={trust_tools}",
            full_prompt,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
            output = stdout.decode("utf-8").strip()

            if proc.returncode != 0:
                stderr_text = stderr.decode("utf-8").strip()
                logger.error(
                    "kiro-cli exited with code %d: %s",
                    proc.returncode,
                    stderr_text,
                )
                output = f"[ERROR] kiro-cli exit code {proc.returncode}: {stderr_text}"

        except asyncio.TimeoutError:
            logger.error("kiro-cli timed out after %d seconds.", timeout_seconds)
            output = f"[ERROR] kiro-cli timed out after {timeout_seconds}s"
        except FileNotFoundError:
            logger.error("kiro-cli not found on PATH.")
            output = "[ERROR] kiro-cli not found on PATH"

        state.output.completion = output
        return state

    return solve
