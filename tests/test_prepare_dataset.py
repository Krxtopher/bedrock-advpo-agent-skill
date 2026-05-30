"""Unit tests for scripts/prepare_dataset.py.

Tests cover placeholder extraction, sample validation, evaluation method
exclusivity, and output format.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Import the module under test
from prepare_dataset import (
    SCHEMA_VERSION,
    build_dataset_record,
    extract_placeholders,
    format_input_variables,
    validate_samples,
)


# =========================================================================
# Placeholder Extraction
# =========================================================================


class TestExtractPlaceholders:
    """Tests for extract_placeholders."""

    def test_single_placeholder(self):
        assert extract_placeholders("Hello {{name}}") == {"name"}

    def test_multiple_placeholders(self):
        assert extract_placeholders("{{a}} and {{b}}") == {"a", "b"}

    def test_no_placeholders(self):
        assert extract_placeholders("Hello world") == set()

    def test_duplicate_placeholders(self):
        assert extract_placeholders("{{x}} {{x}}") == {"x"}


# =========================================================================
# Sample Validation
# =========================================================================


class TestValidateSamples:
    """Tests for validate_samples."""

    def test_valid_text_only_sample(self):
        samples = [{"inputVariables": {"name": "Alice"}}]
        errors = validate_samples(samples, {"name"})
        assert errors == []

    def test_missing_variable(self):
        samples = [{"inputVariables": {"name": "Alice"}}]
        errors = validate_samples(samples, {"name", "age"})
        assert any("missing variables" in e for e in errors)

    def test_extra_variable(self):
        samples = [{"inputVariables": {"name": "Alice", "extra": "val"}}]
        errors = validate_samples(samples, {"name"})
        assert any("extra variables" in e for e in errors)

    def test_multimodal_sample_without_text(self):
        """Valid when inputVariablesMultimodal is present and template has no placeholders."""
        samples = [
            {
                "inputVariablesMultimodal": [
                    {"doc": {"type": "IMAGE", "s3Uri": "s3://bucket/img.png"}}
                ]
            }
        ]
        errors = validate_samples(samples, set())
        assert errors == []

    def test_too_many_multimodal_files(self):
        samples = [
            {
                "inputVariablesMultimodal": [
                    {"a": {"type": "IMAGE", "s3Uri": "s3://b/1.png"}},
                    {"b": {"type": "IMAGE", "s3Uri": "s3://b/2.png"}},
                    {"c": {"type": "IMAGE", "s3Uri": "s3://b/3.png"}},
                ]
            }
        ]
        errors = validate_samples(samples, set())
        assert any("maximum 2 multimodal" in e for e in errors)

    def test_invalid_multimodal_type(self):
        samples = [
            {
                "inputVariablesMultimodal": [
                    {"doc": {"type": "VIDEO", "s3Uri": "s3://b/vid.mp4"}}
                ]
            }
        ]
        errors = validate_samples(samples, set())
        assert any("type must be one of" in e for e in errors)

    def test_missing_s3uri(self):
        samples = [
            {
                "inputVariablesMultimodal": [
                    {"doc": {"type": "IMAGE"}}
                ]
            }
        ]
        errors = validate_samples(samples, set())
        assert any("missing 's3Uri'" in e for e in errors)

    def test_over_100_samples(self):
        samples = [{"inputVariables": {"x": str(i)}} for i in range(101)]
        errors = validate_samples(samples, {"x"})
        assert any("Maximum 100" in e for e in errors)


# =========================================================================
# Evaluation Method Exclusivity (CLI-level validation via subprocess)
# =========================================================================


SCRIPT_PATH = (
    Path(__file__).parent.parent
    / "skills"
    / "bedrock-advanced-prompt-optimization"
    / "scripts"
    / "prepare_dataset.py"
)


@pytest.fixture()
def tmp_samples_file(tmp_path):
    """Create a minimal valid samples file."""
    samples = [{"inputVariables": {"name": "Alice"}}]
    path = tmp_path / "samples.json"
    path.write_text(json.dumps(samples))
    return path


class TestEvalMethodExclusivity:
    """Tests for mutually exclusive evaluation method arguments."""

    def test_multiple_methods_exits_with_error(self, tmp_path, tmp_samples_file):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--output", str(tmp_path / "out.jsonl"),
                "--template-id", "test",
                "--prompt-template", "Hello {{name}}",
                "--samples", str(tmp_samples_file),
                "--steering-criteria", "Be concise",
                "--lambda-arn", "arn:aws:lambda:us-east-1:123:function:eval",
                "--metric-label", "my_metric",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "Choose only ONE" in result.stderr

    def test_llmj_without_model_exits_with_error(self, tmp_path, tmp_samples_file):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--output", str(tmp_path / "out.jsonl"),
                "--template-id", "test",
                "--prompt-template", "Hello {{name}}",
                "--samples", str(tmp_samples_file),
                "--llmj-prompt", "Rate this response",
                "--metric-label", "quality",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "--llmj-model is required" in result.stderr

    def test_lambda_without_metric_label_exits_with_error(self, tmp_path, tmp_samples_file):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--output", str(tmp_path / "out.jsonl"),
                "--template-id", "test",
                "--prompt-template", "Hello {{name}}",
                "--samples", str(tmp_samples_file),
                "--lambda-arn", "arn:aws:lambda:us-east-1:123:function:eval",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "--metric-label is required" in result.stderr

    def test_over_5_steering_criteria_exits_with_error(self, tmp_path, tmp_samples_file):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--output", str(tmp_path / "out.jsonl"),
                "--template-id", "test",
                "--prompt-template", "Hello {{name}}",
                "--samples", str(tmp_samples_file),
                "--steering-criteria", "a", "b", "c", "d", "e", "f",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "Maximum 5" in result.stderr


# =========================================================================
# Output Format
# =========================================================================


class TestOutputFormat:
    """Tests for build_dataset_record and output structure."""

    def test_jsonl_structure(self, tmp_path, tmp_samples_file):
        """Output contains valid JSON on each line."""
        output = tmp_path / "out.jsonl"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--output", str(output),
                "--template-id", "test",
                "--prompt-template", "Hello {{name}}",
                "--samples", str(tmp_samples_file),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        lines = output.read_text().strip().split("\n")
        for line in lines:
            json.loads(line)  # Should not raise

    def test_schema_version(self):
        record = build_dataset_record(
            template_id="test",
            prompt_template="Hello {{name}}",
            samples=[{"inputVariables": {"name": "Alice"}}],
        )
        assert record["version"] == SCHEMA_VERSION

    def test_input_variables_format(self):
        """Variables are formatted as list of single-key objects."""
        result = format_input_variables({"name": "Alice", "age": "30"})
        assert isinstance(result, list)
        assert all(isinstance(item, dict) and len(item) == 1 for item in result)

    def test_append_mode(self, tmp_path, tmp_samples_file):
        """--append adds to existing file without overwriting."""
        output = tmp_path / "out.jsonl"
        # First write
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--output", str(output),
                "--template-id", "first",
                "--prompt-template", "Hello {{name}}",
                "--samples", str(tmp_samples_file),
            ],
            capture_output=True,
            text=True,
        )
        # Second write with --append
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--output", str(output),
                "--template-id", "second",
                "--prompt-template", "Hello {{name}}",
                "--samples", str(tmp_samples_file),
                "--append",
            ],
            capture_output=True,
            text=True,
        )
        lines = output.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["templateId"] == "first"
        assert json.loads(lines[1])["templateId"] == "second"
