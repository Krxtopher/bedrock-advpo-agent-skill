"""Unit tests for scripts/parse_results.py.

Tests cover S3 key derivation and score formatting.
"""

import json

import pytest

from parse_results import format_results, get_results_key


# =========================================================================
# S3 Key Derivation
# =========================================================================


class TestGetResultsKey:
    """Tests for get_results_key."""

    def test_standard_uri(self):
        bucket, key = get_results_key(
            "arn:aws:bedrock:us-east-1:123456789012:advanced-prompt-optimization-job/abc123",
            "s3://bucket/output/",
        )
        assert bucket == "bucket"
        assert key == "output/abc123/advanced_prompt_optimization_results.jsonl"

    def test_uri_without_trailing_slash(self):
        bucket, key = get_results_key(
            "arn:aws:bedrock:us-east-1:123456789012:advanced-prompt-optimization-job/abc123",
            "s3://bucket/output",
        )
        assert bucket == "bucket"
        assert key == "output/abc123/advanced_prompt_optimization_results.jsonl"

    def test_uri_with_no_prefix(self):
        bucket, key = get_results_key(
            "arn:aws:bedrock:us-east-1:123456789012:advanced-prompt-optimization-job/abc123",
            "s3://bucket",
        )
        assert bucket == "bucket"
        assert key == "abc123/advanced_prompt_optimization_results.jsonl"


# =========================================================================
# Score Formatting
# =========================================================================


class TestScoreFormatting:
    """Tests for format_results score display."""

    def _make_results_jsonl(self, original_scores: list[float], optimized_scores: list[float]) -> str:
        """Build a minimal results JSONL string with given scores."""
        dataset = []
        for orig, opt in zip(original_scores, optimized_scores):
            dataset.append({
                "originalPromptDetails": {
                    "originalPromptMetrics": {"score": orig}
                },
                "optimizedPromptDetails": {
                    "optimizedPromptMetrics": {"score": opt}
                },
            })

        record = {
            "promptTemplateId": "test-template",
            "promptOptimizationResults": [
                {
                    "modelId": "test-model",
                    "status": "SUCCESS",
                    "dataset": dataset,
                    "optimizedPromptTemplate": "optimized text",
                }
            ],
        }
        return json.dumps(record)

    def test_score_improvement_displayed(self):
        content = self._make_results_jsonl([0.4, 0.6], [0.7, 0.9])
        output = format_results(content)
        assert "Original prompt avg score" in output
        assert "Optimized prompt avg score" in output
        assert "Improvement" in output

    def test_positive_improvement_shows_plus(self):
        content = self._make_results_jsonl([0.3, 0.3], [0.8, 0.8])
        output = format_results(content)
        assert "+0.5000" in output

    def test_negative_improvement_shows_minus(self):
        content = self._make_results_jsonl([0.8, 0.8], [0.3, 0.3])
        output = format_results(content)
        assert "-0.5000" in output
