# Testing a Lambda Evaluator

Every time you write a Lambda evaluator function, you must also write a local test script that validates the function before deployment. This catches bugs early — a broken evaluator silently produces bad scores, which means Advanced Prompt Optimization optimizes in the wrong direction and the user wastes time and money on a job that looked successful but produced garbage prompts.

## When to Write the Test

Immediately after writing the Lambda function code, before zipping and deploying it.

## What the Test Script Should Do

1. Import the Lambda function's `compute_score` function directly (not via Lambda invocation)
2. Test with realistic sample data drawn from the user's actual ground truth and expected model outputs
3. Verify the return format matches `{"score": float, "scores": [float, ...]}`
4. Test edge cases: perfect match (should score 1.0), complete mismatch (should score 0.0), partial match (should score between 0.0 and 1.0)
5. Test error resilience: malformed input, empty strings, missing keys (should return 0.0, never crash)
6. Print clear pass/fail results so the user can see what's working

## Test Script Conventions

- Name the file `test_evaluator.py` and place it alongside the Lambda function
- Use `pytest` style assertions where possible
- Include at least 3 test cases: one perfect, one partial, one failure
- Use real data from the user's ground truth files when available — synthetic test data is acceptable as a fallback but real data catches real bugs
- Run the test script and confirm all tests pass before proceeding to deployment

## Example Test Structure

```python
"""Test the Lambda evaluator function locally before deployment."""
import json
import sys
from pathlib import Path

# Import the evaluator directly
sys.path.insert(0, str(Path(__file__).parent))
from lambda_function import compute_score


def test_perfect_match():
    """Perfect prediction should score 1.0."""
    preds = ['{"name": "John Doe", "amount": "1500.00"}']
    golds = ['{"name": "John Doe", "amount": "1500.00"}']
    result = compute_score(preds, golds)
    assert result["score"] == 1.0, f"Expected 1.0, got {result['score']}"
    assert len(result["scores"]) == 1


def test_partial_match():
    """Partial match should score between 0.0 and 1.0."""
    preds = ['{"name": "John Doe", "amount": "1600.00"}']
    golds = ['{"name": "John Doe", "amount": "1500.00"}']
    result = compute_score(preds, golds)
    assert 0.0 < result["score"] < 1.0, f"Expected partial score, got {result['score']}"


def test_malformed_input():
    """Malformed input should return 0.0, not crash."""
    preds = ["not valid json"]
    golds = ['{"name": "John Doe"}']
    result = compute_score(preds, golds)
    assert result["score"] == 0.0, f"Expected 0.0 for malformed input, got {result['score']}"


if __name__ == "__main__":
    tests = [test_perfect_match, test_partial_match, test_malformed_input]
    passed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {test.__name__} — {e}")
    print(f"\n{passed}/{len(tests)} tests passed.")
    if passed < len(tests):
        sys.exit(1)
```

Adapt the test data to match the user's specific evaluator logic (e.g., ANLS scoring, exact match, F1). The example above is a starting point — your actual test should use field names and values from the user's ground truth.
