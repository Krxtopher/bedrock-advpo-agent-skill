"""Unit tests for the Lambda evaluator template (examples/lambda-evaluator-template.py).

Tests cover scoring logic, batch scoring, code fence handling, and the Lambda handler.
"""

import importlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()
def evaluator():
    """Import the lambda evaluator template as a module."""
    spec = importlib.util.spec_from_file_location(
        "lambda_evaluator_template",
        Path(__file__).parent.parent
        / "skills"
        / "bedrock-advanced-prompt-optimization"
        / "examples"
        / "lambda-evaluator-template.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# =========================================================================
# Scoring Logic
# =========================================================================


class TestScoreSingle:
    """Tests for _score_single."""

    def test_exact_match_returns_1(self, evaluator):
        gold = json.dumps({"name": "Alice", "age": "30"})
        pred = json.dumps({"name": "Alice", "age": "30"})
        assert evaluator._score_single(pred, gold) == 1.0

    def test_partial_match_returns_fraction(self, evaluator):
        gold = json.dumps({"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"})
        pred = json.dumps({"a": "1", "b": "2", "c": "3", "d": "wrong", "e": "wrong"})
        assert evaluator._score_single(pred, gold) == pytest.approx(0.6)

    def test_no_match_returns_0(self, evaluator):
        gold = json.dumps({"x": "hello", "y": "world"})
        pred = json.dumps({"x": "foo", "y": "bar"})
        assert evaluator._score_single(pred, gold) == 0.0

    def test_empty_gold_returns_0(self, evaluator):
        gold = json.dumps({})
        pred = json.dumps({"a": "1"})
        assert evaluator._score_single(pred, gold) == 0.0

    def test_malformed_pred_json_returns_0(self, evaluator):
        gold = json.dumps({"a": "1"})
        pred = "not valid json {{"
        assert evaluator._score_single(pred, gold) == 0.0

    def test_none_pred_returns_0(self, evaluator):
        gold = json.dumps({"a": "1"})
        assert evaluator._score_single(None, gold) == 0.0

    def test_exception_guard_returns_0(self, evaluator):
        """If scoring logic raises any exception, returns 0.0."""
        gold = "not json at all"
        pred = json.dumps({"a": "1"})
        # gold can't be parsed as JSON → should return 0.0, not raise
        assert evaluator._score_single(pred, gold) == 0.0


# =========================================================================
# Batch Scoring
# =========================================================================


class TestComputeScore:
    """Tests for compute_score."""

    def test_averages_correctly(self, evaluator):
        # Set up preds/golds that produce known scores: 1.0, 0.5, 0.0
        gold_full = json.dumps({"a": "1", "b": "2"})
        pred_full = json.dumps({"a": "1", "b": "2"})  # 1.0

        gold_half = json.dumps({"a": "1", "b": "2"})
        pred_half = json.dumps({"a": "1", "b": "wrong"})  # 0.5

        gold_none = json.dumps({"a": "1", "b": "2"})
        pred_none = json.dumps({"a": "wrong", "b": "wrong"})  # 0.0

        result = evaluator.compute_score(
            [pred_full, pred_half, pred_none],
            [gold_full, gold_half, gold_none],
        )
        assert result["score"] == pytest.approx(0.5)
        assert result["scores"] == pytest.approx([1.0, 0.5, 0.0])

    def test_empty_batch(self, evaluator):
        result = evaluator.compute_score([], [])
        assert result == {"score": 0.0, "scores": []}


# =========================================================================
# Code Fence Handling
# =========================================================================


class TestCodeFences:
    """Tests for strip_code_fences and parse_json_output."""

    def test_strip_code_fences_removes_json_wrapper(self, evaluator):
        text = '```json\n{"key": "value"}\n```'
        assert evaluator.strip_code_fences(text) == '{"key": "value"}'

    def test_strip_code_fences_passes_through_clean_text(self, evaluator):
        text = '{"key": "value"}'
        assert evaluator.strip_code_fences(text) == '{"key": "value"}'

    def test_tolerant_mode_parses_with_fences(self, evaluator):
        text = '```json\n{"key": "value"}\n```'
        with patch.object(evaluator, "TOLERANT_CODE_FENCES", True):
            result = evaluator.parse_json_output(text)
        assert result == {"key": "value"}

    def test_strict_mode_raises_with_fences(self, evaluator):
        text = '```json\n{"key": "value"}\n```'
        evaluator.TOLERANT_CODE_FENCES = False
        try:
            with pytest.raises(ValueError, match="strict mode"):
                evaluator.parse_json_output(text)
        finally:
            evaluator.TOLERANT_CODE_FENCES = True


# =========================================================================
# Lambda Handler
# =========================================================================


class TestLambdaHandler:
    """Tests for lambda_handler."""

    def test_correct_event_keys(self, evaluator):
        event = {
            "preds": [json.dumps({"a": "1"})],
            "golds": [json.dumps({"a": "1"})],
        }
        result = evaluator.lambda_handler(event, None)
        assert result["score"] == 1.0
        assert result["scores"] == [1.0]

    def test_missing_keys_defaults_to_empty(self, evaluator):
        result = evaluator.lambda_handler({}, None)
        assert result == {"score": 0.0, "scores": []}

    def test_return_format(self, evaluator):
        event = {
            "preds": [json.dumps({"a": "1"}), json.dumps({"a": "wrong"})],
            "golds": [json.dumps({"a": "1"}), json.dumps({"a": "1"})],
        }
        result = evaluator.lambda_handler(event, None)
        assert isinstance(result["score"], float)
        assert isinstance(result["scores"], list)
        assert all(isinstance(s, float) for s in result["scores"])
