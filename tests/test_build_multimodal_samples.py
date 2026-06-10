"""Unit tests for scripts/build_multimodal_samples.py.

Tests cover file discovery (with and without ground truth) and output format.
These tests exercise the script via subprocess to test CLI behavior, and
validate the output JSON structure.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).parent.parent
    / "skills"
    / "bedrock-advanced-prompt-optimization"
    / "scripts"
    / "build_multimodal_samples.py"
)


@pytest.fixture()
def assets_with_gt(tmp_path):
    """Create an assets directory with ground truth files and matching documents."""
    assets = tmp_path / "assets"
    assets.mkdir()

    # Create ground truth files
    gt1 = {"name": "Alice", "amount": "100.00"}
    (assets / "check1-ground_truth.json").write_text(json.dumps(gt1))
    gt2 = {"name": "Bob", "amount": "200.00"}
    (assets / "check2-ground_truth.json").write_text(json.dumps(gt2))

    # Create matching document files
    (assets / "check1.png").write_bytes(b"fake png data")
    (assets / "check2.png").write_bytes(b"fake png data")

    return assets


@pytest.fixture()
def assets_without_gt(tmp_path):
    """Create an assets directory with only document files (no ground truth)."""
    assets = tmp_path / "assets"
    assets.mkdir()

    (assets / "doc1.png").write_bytes(b"fake png")
    (assets / "doc2.png").write_bytes(b"fake png")
    (assets / "doc3.png").write_bytes(b"fake png")

    return assets


# =========================================================================
# File Discovery
# =========================================================================


class TestFileDiscovery:
    """Tests for file discovery logic."""

    def test_with_ground_truth_pairs_files(self, assets_with_gt, tmp_path):
        output = tmp_path / "samples.json"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--assets-dir", str(assets_with_gt),
                "--bucket", "test-bucket",
                "--s3-prefix", "prefix",
                "--output", str(output),
                "--skip-upload",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        samples = json.loads(output.read_text())
        assert len(samples) == 2

    def test_without_ground_truth_discovers_all_docs(self, assets_without_gt, tmp_path):
        output = tmp_path / "samples.json"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--assets-dir", str(assets_without_gt),
                "--bucket", "test-bucket",
                "--s3-prefix", "prefix",
                "--output", str(output),
                "--no-ground-truth",
                "--skip-upload",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        samples = json.loads(output.read_text())
        assert len(samples) == 3

    def test_missing_document_for_ground_truth_skips_with_warning(self, tmp_path):
        """Skips with warning when no matching document exists."""
        assets = tmp_path / "assets"
        assets.mkdir()
        gt = {"name": "Alice"}
        (assets / "orphan-ground_truth.json").write_text(json.dumps(gt))
        # No matching orphan.png

        # Also need at least one valid pair or the script will error
        (assets / "valid-ground_truth.json").write_text(json.dumps({"x": "1"}))
        (assets / "valid.png").write_bytes(b"fake")

        output = tmp_path / "samples.json"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--assets-dir", str(assets),
                "--bucket", "test-bucket",
                "--s3-prefix", "prefix",
                "--output", str(output),
                "--skip-upload",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "WARNING" in result.stdout or "WARNING" in result.stderr or "skipping" in result.stdout.lower()
        samples = json.loads(output.read_text())
        assert len(samples) == 1  # Only the valid pair

    def test_no_ground_truth_files_exits_with_error(self, tmp_path):
        """Exits with error when no GT files found (suggests --no-ground-truth)."""
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "doc.png").write_bytes(b"fake")  # No GT files

        output = tmp_path / "samples.json"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--assets-dir", str(assets),
                "--bucket", "test-bucket",
                "--s3-prefix", "prefix",
                "--output", str(output),
                "--skip-upload",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "--no-ground-truth" in result.stderr

    def test_custom_gt_suffix(self, tmp_path):
        """Respects --gt-suffix for pairing."""
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "item_gt.json").write_text(json.dumps({"a": "1"}))
        (assets / "item.png").write_bytes(b"fake")

        output = tmp_path / "samples.json"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--assets-dir", str(assets),
                "--bucket", "test-bucket",
                "--s3-prefix", "prefix",
                "--output", str(output),
                "--skip-upload",
                "--gt-suffix", "_gt.json",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        samples = json.loads(output.read_text())
        assert len(samples) == 1


# =========================================================================
# Output Format
# =========================================================================


class TestOutputFormat:
    """Tests for the output samples JSON structure."""

    def test_sample_structure_with_gt(self, assets_with_gt, tmp_path):
        """Contains inputVariablesMultimodal and referenceResponse."""
        output = tmp_path / "samples.json"
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--assets-dir", str(assets_with_gt),
                "--bucket", "test-bucket",
                "--s3-prefix", "prefix",
                "--output", str(output),
                "--skip-upload",
            ],
            capture_output=True,
            text=True,
        )
        samples = json.loads(output.read_text())
        sample = samples[0]
        assert "inputVariablesMultimodal" in sample
        assert "referenceResponse" in sample

    def test_sample_structure_no_gt(self, assets_without_gt, tmp_path):
        """Contains inputVariablesMultimodal only, no referenceResponse."""
        output = tmp_path / "samples.json"
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--assets-dir", str(assets_without_gt),
                "--bucket", "test-bucket",
                "--s3-prefix", "prefix",
                "--output", str(output),
                "--no-ground-truth",
                "--skip-upload",
            ],
            capture_output=True,
            text=True,
        )
        samples = json.loads(output.read_text())
        sample = samples[0]
        assert "inputVariablesMultimodal" in sample
        assert "referenceResponse" not in sample

    def test_shared_input_variables(self, assets_without_gt, tmp_path):
        """When --input-variables is provided, each sample includes them."""
        vars_file = tmp_path / "vars.json"
        vars_file.write_text(json.dumps({"prompt": "Extract the amount"}))

        output = tmp_path / "samples.json"
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--assets-dir", str(assets_without_gt),
                "--bucket", "test-bucket",
                "--s3-prefix", "prefix",
                "--output", str(output),
                "--no-ground-truth",
                "--skip-upload",
                "--input-variables", str(vars_file),
            ],
            capture_output=True,
            text=True,
        )
        samples = json.loads(output.read_text())
        for sample in samples:
            assert "inputVariables" in sample

    def test_s3_uri_construction(self, assets_with_gt, tmp_path):
        """Uses s3://{bucket}/{s3-prefix}/{filename}."""
        output = tmp_path / "samples.json"
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--assets-dir", str(assets_with_gt),
                "--bucket", "my-bucket",
                "--s3-prefix", "my/prefix",
                "--output", str(output),
                "--skip-upload",
            ],
            capture_output=True,
            text=True,
        )
        samples = json.loads(output.read_text())
        sample = samples[0]
        multimodal = sample["inputVariablesMultimodal"][0]
        name = list(multimodal.keys())[0]
        s3_uri = multimodal[name]["s3Uri"]
        assert s3_uri.startswith("s3://my-bucket/my/prefix/")
