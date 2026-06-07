"""Inspect AI task definitions for the Advanced Prompt Optimization skill.

This module defines two tasks:
- `skill_eval_deterministic`: Runs evals with deterministic Python scorers.
- `skill_eval_llm_judge`: Runs evals graded by an LLM judge on Bedrock.

Usage:
    # Deterministic evals only (no Bedrock judge needed):
    inspect eval inspect_evals/task.py@skill_eval_deterministic --model none

    # LLM-judge evals (requires Bedrock access):
    inspect eval inspect_evals/task.py@skill_eval_llm_judge \
        --model none \
        --model-role grader=anthropic/bedrock/us.anthropic.claude-opus-4-6-v1

    # All evals together:
    inspect eval inspect_evals/task.py --model none \
        --model-role grader=anthropic/bedrock/us.anthropic.claude-opus-4-6-v1
"""

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so sibling package imports work
# when Inspect loads this file directly.
_REPO_ROOT = str(Path(__file__).parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.scorer import model_graded_qa

from inspect_evals.scorers import (
    does_not_contain_re_compile,
    does_not_use_advpo_abbreviation,
    metadata_dispatch_scorer,
    no_numbered_model_list,
    score_range_recommends_zero_to_one,
    single_question_per_turn,
)
from inspect_evals.solver import kiro_cli_headless

DATASET_PATH = Path(__file__).parent / "dataset.json"


def _load_filtered_dataset(scorer_type: str) -> list[Sample]:
    """Load samples from dataset.json filtered by scorer_type metadata."""
    all_samples = json_dataset(str(DATASET_PATH))
    return [s for s in all_samples if s.metadata and s.metadata.get("scorer_type") == scorer_type]


@task
def skill_eval_deterministic() -> Task:
    """Evals with deterministic Python scorers — no LLM judge needed.

    Uses the metadata_dispatch scorer which routes each sample to its
    designated scorer based on the 'scorer_name' metadata field.
    """
    return Task(
        dataset=_load_filtered_dataset("deterministic"),
        solver=kiro_cli_headless(),
        scorer=metadata_dispatch_scorer(),
    )


@task
def skill_eval_llm_judge() -> Task:
    """Evals graded by an LLM judge (model_graded_qa) on Bedrock.

    The judge model is specified at eval time via --model-role grader=...
    The target field in each sample contains the grading criteria.
    """
    return Task(
        dataset=_load_filtered_dataset("llm_judge"),
        solver=kiro_cli_headless(),
        scorer=model_graded_qa(),
    )
