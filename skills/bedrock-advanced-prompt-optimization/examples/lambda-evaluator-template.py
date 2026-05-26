"""Lambda evaluator template for AdvPO.

IMPORTANT: Do NOT modify the lambda_handler function or the event key names.
AdvPO sends events with exactly these keys:
  - "preds": list of model output strings
  - "golds": list of reference/ground truth strings

Customize ONLY the compute_score function to implement your scoring logic.

SANDBOX RESTRICTIONS:
  AdvPO validates Lambda evaluator code in a sandbox that blocks certain
  Python builtins considered dangerous. Notably, `compile()` is blocked —
  which means `re.compile()` and any use of the `re` module will cause the
  job to fail with: "Metric code validation failed: Uses potentially
  dangerous builtin: compile()"

  Avoid `re` entirely in evaluator functions. Use string methods (startswith,
  endswith, split, strip, replace) for text manipulation instead. The
  `strip_code_fences()` utility below handles the most common case where
  regex would otherwise be tempting.
"""

import json


# =============================================================================
# HANDLER — DO NOT MODIFY
# =============================================================================

def lambda_handler(event: dict, context) -> dict:
    """AWS Lambda entry point. Called by the AdvPO service.

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

    This implementation avoids the `re` module, which is blocked by the AdvPO
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

    Returns a float between 0.0 and 1.0. Must never raise an exception.
    """
    try:
        pred_obj = parse_json_output(pred)
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0.0

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


def _normalize(value) -> str:
    """Normalize a value for comparison."""
    if value is None:
        return ""
    return str(value).strip().lower()
