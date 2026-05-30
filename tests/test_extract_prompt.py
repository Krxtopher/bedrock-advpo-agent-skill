"""Unit tests for scripts/extract_prompt.py.

Tests cover brace unescaping and template/model selection logic.
"""

import json

import pytest

from extract_prompt import extract_optimized_prompt


# =========================================================================
# Brace Unescaping
# =========================================================================


class TestBraceUnescaping:
    """Tests for double-brace to single-brace conversion."""

    def test_double_braces_converted(self):
        """{{name}} in result becomes {name} in output."""
        content = json.dumps({
            "promptTemplateId": "t1",
            "promptOptimizationResults": [
                {
                    "modelId": "m1",
                    "status": "SUCCESS",
                    "optimizedPromptTemplate": "Hello {{name}}, welcome to {{place}}",
                }
            ],
        })
        result = extract_optimized_prompt(content)
        assert result == "Hello {name}, welcome to {place}"

    def test_mixed_content_preserved(self):
        """Only {{ and }} pairs are unescaped, other text preserved."""
        content = json.dumps({
            "promptTemplateId": "t1",
            "promptOptimizationResults": [
                {
                    "modelId": "m1",
                    "status": "SUCCESS",
                    "optimizedPromptTemplate": "Use {{var}} in your JSON: {literal}",
                }
            ],
        })
        result = extract_optimized_prompt(content)
        # {{var}} → {var}, but {literal} stays as-is since replace("{{","{")
        # only affects double braces
        assert "{var}" in result


# =========================================================================
# Template/Model Selection
# =========================================================================


class TestTemplateModelSelection:
    """Tests for template and model selection logic."""

    def _make_content(self, templates: list[dict]) -> str:
        """Build multi-line JSONL from template records."""
        return "\n".join(json.dumps(t) for t in templates)

    def test_single_template_single_model(self):
        """Extracts without requiring --template-id or --model."""
        content = json.dumps({
            "promptTemplateId": "t1",
            "promptOptimizationResults": [
                {
                    "modelId": "m1",
                    "status": "SUCCESS",
                    "optimizedPromptTemplate": "result text",
                }
            ],
        })
        result = extract_optimized_prompt(content)
        assert result == "result text"

    def test_multiple_templates_without_template_id_uses_first(self, capsys):
        """Uses first template and prints warning."""
        records = [
            {
                "promptTemplateId": "t1",
                "promptOptimizationResults": [
                    {"modelId": "m1", "status": "SUCCESS", "optimizedPromptTemplate": "first"}
                ],
            },
            {
                "promptTemplateId": "t2",
                "promptOptimizationResults": [
                    {"modelId": "m1", "status": "SUCCESS", "optimizedPromptTemplate": "second"}
                ],
            },
        ]
        content = self._make_content(records)
        result = extract_optimized_prompt(content)
        assert result == "first"
        captured = capsys.readouterr()
        assert "Multiple templates" in captured.err

    def test_multiple_models_without_model_uses_first(self, capsys):
        """Uses first model and prints warning."""
        content = json.dumps({
            "promptTemplateId": "t1",
            "promptOptimizationResults": [
                {"modelId": "m1", "status": "SUCCESS", "optimizedPromptTemplate": "from-m1"},
                {"modelId": "m2", "status": "SUCCESS", "optimizedPromptTemplate": "from-m2"},
            ],
        })
        result = extract_optimized_prompt(content)
        assert result == "from-m1"
        captured = capsys.readouterr()
        assert "Multiple models" in captured.err

    def test_nonexistent_template_id_exits_with_error(self):
        content = json.dumps({
            "promptTemplateId": "t1",
            "promptOptimizationResults": [
                {"modelId": "m1", "status": "SUCCESS", "optimizedPromptTemplate": "text"}
            ],
        })
        with pytest.raises(SystemExit):
            extract_optimized_prompt(content, template_id="nonexistent")

    def test_nonexistent_model_exits_with_error(self):
        content = json.dumps({
            "promptTemplateId": "t1",
            "promptOptimizationResults": [
                {"modelId": "m1", "status": "SUCCESS", "optimizedPromptTemplate": "text"}
            ],
        })
        with pytest.raises(SystemExit):
            extract_optimized_prompt(content, model_id="nonexistent")

    def test_non_success_status_prints_warning(self, capsys):
        """Prints warning but still extracts."""
        content = json.dumps({
            "promptTemplateId": "t1",
            "promptOptimizationResults": [
                {"modelId": "m1", "status": "FAILED", "optimizedPromptTemplate": "partial"}
            ],
        })
        result = extract_optimized_prompt(content)
        assert result == "partial"
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
