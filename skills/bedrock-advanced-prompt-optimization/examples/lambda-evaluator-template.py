"""Lambda evaluator template for Advanced Prompt Optimization.

IMPORTANT: Do NOT modify the lambda_handler function or the event key names.
Advanced Prompt Optimization sends events with exactly these keys:
  - "preds": list of model output strings
  - "golds": list of reference/ground truth strings

Customize ONLY the compute_score function to implement your scoring logic.

SANDBOX RESTRICTIONS:
  Customer evaluator code is statically scanned before deployment. Any function
  literally named `compile`, `exec`, `eval`, `__import__`, `globals`, `locals`,
  `breakpoint`, `exit`, `quit`, or `open` is rejected. This means `re.compile()`
  is blocked — but `re.search()`, `re.match()`, `re.findall()`, and `re.sub()`
  all work normally and accept the pattern as a string argument.

  Imports that touch the filesystem, network, or process state are also blocked:
  os, subprocess, shutil, socket, ctypes, multiprocessing, signal, pickle,
  shelve, marshal, mmap, http, ftplib, smtplib, telnetlib, xmlrpc, webbrowser,
  pty, fcntl, resource. Use stdlib equivalents (json, math, datetime, statistics,
  hashlib, etc.) and the approved third-party metric libraries instead.

  Approved third-party libraries: numpy, scipy, pandas, scikit-learn, nltk,
  rouge_score, sacrebleu, evaluate, rapidfuzz, editdistance, jiwer, regex,
  transformers, torch, sentence_transformers, bert_score.
"""

import json


# Optional: declare external dependencies explicitly. If present, this overrides
# import inference. Use pip-style version specifiers.
DEPENDENCIES = [
    # "numpy>=1.20",
    # "scikit-learn",
]


# =============================================================================
# HANDLER — DO NOT MODIFY
# =============================================================================

def lambda_handler(event: dict, context) -> dict:
    """AWS Lambda entry point. Called by the Advanced Prompt Optimization service.

    Event format (fixed, do not change key names):
    {
        "preds": ["model_output_1", "model_output_2", ...],
        "golds": ["reference_response_1", "reference_response_2", ...]
    }

    Must return:
    {
        "score": float,    # average score across all samples (0.0 to 1.0)
        "scores": [float]  # per-sample scores (0.0 to 1.0 each)
    }
    """
    preds = event.get("preds", [])
    golds = event.get("golds", [])
    return compute_score(preds, golds)


# =============================================================================
# SCORING LOGIC — CUSTOMIZE BELOW THIS LINE
# =============================================================================

# Set to True to strip Markdown code fences before parsing JSON (tolerant mode).
# Set to False to score 0.0 if the output is wrapped in code fences (strict mode).
TOLERANT_CODE_FENCES = True


def strip_code_fences(text: str) -> str:
    """Remove Markdown code fences (```json ... ``` or ``` ... ```) from text.

    Many models wrap JSON output in code fences. Use this before json.loads()
    to handle that gracefully without penalizing otherwise-correct output.

    This implementation avoids the `re` module, which is blocked by the Advanced Prompt Optimization
    sandbox (see module docstring for details).
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.split("\n")
    # Remove first line (```json or ```) and last line (```)
    if lines[-1].strip() == "```":
        lines = lines[1:-1]
    elif lines[-1].strip().endswith("```"):
        lines[-1] = lines[-1].strip()[:-3]
        lines = lines[1:]
    else:
        lines = lines[1:]
    return "\n".join(lines).strip()


def has_code_fences(text: str) -> bool:
    """Check whether text is wrapped in Markdown code fences."""
    stripped = text.strip()
    return stripped.startswith("```") and "```" in stripped[3:]


def parse_json_output(text: str) -> dict:
    """Parse model output as JSON, respecting the TOLERANT_CODE_FENCES setting.

    - Tolerant mode: strips code fences before parsing.
    - Strict mode: returns empty dict (triggering score 0.0) if fences are present.

    Raises json.JSONDecodeError or ValueError on parse failure.
    """
    if text is None:
        raise ValueError("None input")
    if has_code_fences(text):
        if not TOLERANT_CODE_FENCES:
            raise ValueError("Output wrapped in code fences (strict mode)")
        text = strip_code_fences(text)
    return json.loads(text)


def compute_score(preds: list[str], golds: list[str]) -> dict:
    """Score a batch of predictions against references.

    Args:
        preds: Model output strings (one per evaluation sample).
        golds: Ground truth strings from referenceResponse (one per sample).

    Returns:
        {"score": float, "scores": [float, ...]}
        - "score" is the average across all samples
        - "scores" is the list of per-sample scores
        - All values must be between 0.0 and 1.0
    """
    scores = []
    for pred, gold in zip(preds, golds):
        scores.append(_score_single(pred, gold))

    avg_score = sum(scores) / len(scores) if scores else 0.0
    return {"score": avg_score, "scores": scores}


def _score_single(pred: str, gold: str) -> float:
    """Score a single prediction against its reference.

    Replace this with your actual scoring logic. This example does a simple
    exact-match comparison of JSON fields.

    Returns a float between 0.0 and 1.0. Must never raise an exception —
    any error becomes 0.0 so one bad sample doesn't fail the whole batch.
    """
    try:
        pred_obj = parse_json_output(pred)

        try:
            gold_obj = json.loads(gold)
        except (json.JSONDecodeError, TypeError):
            return 0.0

        if not gold_obj:
            return 0.0

        # Example: average exact match across all fields in the ground truth
        matches = 0
        total = 0
        for key, expected in gold_obj.items():
            total += 1
            actual = pred_obj.get(key)
            if _normalize(actual) == _normalize(expected):
                matches += 1

        return matches / total if total > 0 else 0.0
    except Exception as exc:
        print(f"score error: {type(exc).__name__}: {exc}")
        return 0.0


def _normalize(value) -> str:
    """Normalize a value for comparison."""
    if value is None:
        return ""
    return str(value).strip().lower()
