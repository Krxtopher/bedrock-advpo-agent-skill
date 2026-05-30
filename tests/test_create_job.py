"""Unit tests for scripts/create_job.py.

Tests cover job name suffix generation, model access checks, CRIS inference
profile checks, multimodal compatibility, tag parsing, and argument validation.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from create_job import (
    check_inference_profile,
    check_model_access,
    check_multimodal_compatible,
    generate_job_suffix,
)


SCRIPT_PATH = (
    Path(__file__).parent.parent
    / "skills"
    / "bedrock-advanced-prompt-optimization"
    / "scripts"
    / "create_job.py"
)


# =========================================================================
# Job Name Suffix
# =========================================================================


class TestJobNameSuffix:
    """Tests for generate_job_suffix."""

    def test_suffix_is_4_char_hex(self):
        suffix = generate_job_suffix()
        assert len(suffix) == 4
        int(suffix, 16)  # Should not raise — valid hex

    def test_suffix_is_unique(self):
        """Two calls produce different suffixes (time-based)."""
        s1 = generate_job_suffix()
        s2 = generate_job_suffix()
        # Extremely unlikely to collide given nanosecond timestamps
        assert s1 != s2


# =========================================================================
# Model Access Check
# =========================================================================


class TestCheckModelAccess:
    """Tests for check_model_access."""

    def test_accessible_model(self):
        client = MagicMock()
        client.get_foundation_model.return_value = {
            "modelDetails": {
                "modelLifecycle": {"status": "ACTIVE"},
                "inputModalities": ["TEXT"],
            }
        }
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"inferenceProfileSummaries": []}
        ]
        client.get_paginator.return_value = paginator

        result = check_model_access(client, ["anthropic.claude-v2"], "us-east-1")
        assert result == []

    def test_inaccessible_model_resource_not_found(self):
        client = MagicMock()
        client.get_foundation_model.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "GetFoundationModel",
        )
        paginator = MagicMock()
        paginator.paginate.return_value = [{"inferenceProfileSummaries": []}]
        client.get_paginator.return_value = paginator

        result = check_model_access(client, ["fake.model-v1"], "us-east-1")
        assert "fake.model-v1" in result

    def test_legacy_status_prints_warning_but_does_not_block(self, capsys):
        client = MagicMock()
        client.get_foundation_model.return_value = {
            "modelDetails": {
                "modelLifecycle": {"status": "LEGACY"},
                "inputModalities": ["TEXT"],
            }
        }
        paginator = MagicMock()
        paginator.paginate.return_value = [{"inferenceProfileSummaries": []}]
        client.get_paginator.return_value = paginator

        result = check_model_access(client, ["anthropic.claude-v1"], "us-east-1")
        assert result == []
        captured = capsys.readouterr()
        assert "LEGACY" in captured.err

    def test_throttling_error_prints_warning_but_does_not_block(self, capsys):
        client = MagicMock()
        client.get_foundation_model.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Slow down"}},
            "GetFoundationModel",
        )
        paginator = MagicMock()
        paginator.paginate.return_value = [{"inferenceProfileSummaries": []}]
        client.get_paginator.return_value = paginator

        result = check_model_access(client, ["anthropic.claude-v2"], "us-east-1")
        assert result == []
        captured = capsys.readouterr()
        assert "WARNING" in captured.err


# =========================================================================
# CRIS Inference Profile Check
# =========================================================================


class TestCheckInferenceProfile:
    """Tests for check_inference_profile."""

    def test_non_prefixed_model_id(self):
        """Non-prefixed model ID returns True (no check needed)."""
        client = MagicMock()
        assert check_inference_profile(client, "anthropic.claude-v2") is True

    def test_prefixed_id_with_long_first_segment(self):
        """Long first segment means it's not a region prefix."""
        client = MagicMock()
        assert check_inference_profile(client, "anthropic.claude-v2") is True

    def test_prefixed_id_found_in_profiles_list(self):
        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "inferenceProfileSummaries": [
                    {"inferenceProfileId": "us.anthropic.claude-sonnet-4-5-20250929-v1:0"}
                ]
            }
        ]
        client.get_paginator.return_value = paginator

        result = check_inference_profile(
            client, "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        )
        assert result is True

    def test_prefixed_id_not_found_in_profiles_list(self):
        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"inferenceProfileSummaries": []}
        ]
        client.get_paginator.return_value = paginator

        result = check_inference_profile(
            client, "us.anthropic.claude-nonexistent-v1:0"
        )
        assert result is False

    def test_client_error_during_listing_returns_true(self):
        """Fail-open: if we can't list profiles, don't block."""
        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Denied"}},
            "ListInferenceProfiles",
        )
        client.get_paginator.return_value = paginator

        result = check_inference_profile(
            client, "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        )
        assert result is True


# =========================================================================
# Multimodal Compatibility Check
# =========================================================================


class TestCheckMultimodalCompatible:
    """Tests for check_multimodal_compatible."""

    def test_dataset_has_no_multimodal(self):
        client = MagicMock()
        result, msg = check_multimodal_compatible(client, "any-model", False)
        assert result is True

    def test_model_supports_image_input(self):
        client = MagicMock()
        client.get_foundation_model.return_value = {
            "modelDetails": {"inputModalities": ["TEXT", "IMAGE"]}
        }
        result, msg = check_multimodal_compatible(
            client, "anthropic.claude-v2", True
        )
        assert result is True

    def test_model_is_text_only(self):
        client = MagicMock()
        client.get_foundation_model.return_value = {
            "modelDetails": {"inputModalities": ["TEXT"]}
        }
        result, msg = check_multimodal_compatible(
            client, "anthropic.claude-v2", True
        )
        assert result is False
        assert "does not accept multimodal" in msg

    def test_client_error_returns_true(self):
        """Fail-open on errors."""
        client = MagicMock()
        client.get_foundation_model.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Denied"}},
            "GetFoundationModel",
        )
        result, msg = check_multimodal_compatible(
            client, "anthropic.claude-v2", True
        )
        assert result is True


# =========================================================================
# Tag Parsing (CLI-level)
# =========================================================================


class TestTagParsing:
    """Tests for tag parsing via CLI."""

    def test_invalid_tag_format_exits_with_error(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--job-name", "test",
                "--input-s3-uri", "s3://bucket/input.jsonl",
                "--output-s3-uri", "s3://bucket/output/",
                "--models", "anthropic.claude-v2",
                "--region", "us-east-1",
                "--skip-preflight",
                "--tags", "invalid-no-equals",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "Invalid tag format" in result.stderr


# =========================================================================
# Argument Validation (CLI-level)
# =========================================================================


class TestArgumentValidation:
    """Tests for CLI argument validation."""

    def test_over_5_models_exits_with_error(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--job-name", "test",
                "--input-s3-uri", "s3://bucket/input.jsonl",
                "--output-s3-uri", "s3://bucket/output/",
                "--models", "m1", "m2", "m3", "m4", "m5", "m6",
                "--region", "us-east-1",
                "--skip-preflight",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "Maximum 5 models" in result.stderr
