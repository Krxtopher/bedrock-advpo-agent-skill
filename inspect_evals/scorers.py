"""Scorers for the Advanced Prompt Optimization skill evals.

This module provides:
- Deterministic Python scorers for assertions that can be checked with code.
- A configured model_graded_qa scorer for subjective assertions judged by an
  LLM on Bedrock.
"""

import re

from inspect_ai.scorer import (
    Score,
    Target,
    accuracy,
    scorer,
    stderr,
)
from inspect_ai.solver import TaskState


# ---------------------------------------------------------------------------
# Deterministic scorers
# ---------------------------------------------------------------------------


@scorer(metrics=[accuracy(), stderr()])
def does_not_contain_re_compile():
    """Passes if the output does NOT contain 're.compile'."""

    async def score(state: TaskState, target: Target) -> Score:
        output = state.output.completion or ""
        if "re.compile" in output:
            return Score(
                value="I",
                explanation="Output contains 're.compile'.",
            )
        return Score(value="C", explanation="No 're.compile' found.")

    return score


@scorer(metrics=[accuracy(), stderr()])
def does_not_use_advpo_abbreviation():
    """Passes if the output does NOT use the abbreviation 'AdvPO'."""

    async def score(state: TaskState, target: Target) -> Score:
        output = state.output.completion or ""
        if re.search(r"\bAdvPO\b", output):
            return Score(
                value="I",
                explanation="Output uses the abbreviation 'AdvPO'.",
            )
        return Score(value="C", explanation="No 'AdvPO' abbreviation found.")

    return score


@scorer(metrics=[accuracy(), stderr()])
def no_numbered_model_list():
    """Passes if the output does NOT present models as a numbered list."""

    async def score(state: TaskState, target: Target) -> Score:
        output = state.output.completion or ""
        # Heuristic: look for patterns like "1. Claude" or "1) Nova"
        pattern = r"^\s*\d+[\.\)]\s+\S+.*(?:model|claude|nova|titan|llama|mistral)"
        if re.search(pattern, output, re.MULTILINE | re.IGNORECASE):
            return Score(
                value="I",
                explanation="Output contains a numbered list of models.",
            )
        return Score(value="C", explanation="No numbered model list found.")

    return score


@scorer(metrics=[accuracy(), stderr()])
def single_question_per_turn():
    """Passes if the output contains at most one question mark sequence.

    This is a heuristic — it counts distinct question-mark-terminated sentences.
    A single question with sub-clauses is acceptable.
    """

    async def score(state: TaskState, target: Target) -> Score:
        output = state.output.completion or ""
        # Split on sentence boundaries ending with '?'
        questions = re.findall(r"[^.!?]*\?", output)
        if len(questions) > 1:
            return Score(
                value="I",
                explanation=f"Output contains {len(questions)} questions.",
            )
        return Score(value="C", explanation="At most one question found.")

    return score


@scorer(metrics=[accuracy(), stderr()])
def score_range_recommends_zero_to_one():
    """Passes if the output recommends the 0.0–1.0 range and does NOT recommend 0–100."""

    async def score(state: TaskState, target: Target) -> Score:
        output = state.output.completion or ""
        recommends_01 = bool(
            re.search(r"0\.0\s*(to|–|—|-)\s*1\.0", output)
            or re.search(r"0\s*(to|–|—|-)\s*1\b", output)
        )
        recommends_100 = bool(re.search(r"0\s*(to|–|—|-)\s*100\b", output))

        if recommends_01 and not recommends_100:
            return Score(value="C", explanation="Recommends 0–1 range.")
        if recommends_100:
            return Score(value="I", explanation="Recommends 0–100 range.")
        return Score(
            value="I",
            explanation="Does not clearly recommend the 0.0–1.0 range.",
        )

    return score


# ---------------------------------------------------------------------------
# Composite dispatcher scorer
# ---------------------------------------------------------------------------

# Registry mapping scorer_name metadata values to scorer functions.
_SCORER_REGISTRY: dict[str, callable] = {}


def _register_scorers() -> None:
    """Populate the scorer registry. Called once at module load."""
    _SCORER_REGISTRY["single_question_per_turn"] = single_question_per_turn
    _SCORER_REGISTRY["no_numbered_model_list"] = no_numbered_model_list
    _SCORER_REGISTRY["does_not_use_advpo_abbreviation"] = does_not_use_advpo_abbreviation
    _SCORER_REGISTRY["score_range_recommends_zero_to_one"] = score_range_recommends_zero_to_one
    _SCORER_REGISTRY["does_not_contain_re_compile"] = does_not_contain_re_compile


_register_scorers()


@scorer(metrics=[accuracy(), stderr()])
def metadata_dispatch_scorer():
    """Routes each sample to its designated scorer based on metadata.scorer_name.

    This avoids running all scorers against all samples. Each sample is scored
    only by the scorer it was designed for.
    """

    async def score(state: TaskState, target: Target) -> Score:
        scorer_name = ""
        if state.metadata:
            scorer_name = state.metadata.get("scorer_name", "")

        if not scorer_name or scorer_name not in _SCORER_REGISTRY:
            return Score(
                value="I",
                explanation=f"No scorer found for scorer_name='{scorer_name}'.",
            )

        # Instantiate the scorer and call its inner score function.
        scorer_instance = _SCORER_REGISTRY[scorer_name]()
        # The @scorer decorator wraps the function; we need to call the
        # returned scorer's __call__ which expects (state, target).
        return await scorer_instance(state, target)

    return score
