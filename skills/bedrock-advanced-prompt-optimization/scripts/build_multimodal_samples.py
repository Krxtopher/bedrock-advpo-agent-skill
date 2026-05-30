"""Build an Advanced Prompt Optimization samples JSON file from local multimodal (image/PDF) files.

This script is only needed for multimodal datasets — where each evaluation
sample includes a document image or PDF alongside the prompt. For text-only
datasets, create samples.json directly (see references/dataset-schema.md for
the format).

Supports two modes:

1. With ground truth (default): Pairs each document with its ground truth
   JSON as the referenceResponse. Ground truth files must follow the naming
   convention: <base-name>-ground_truth.json

2. Without ground truth (--no-ground-truth): Discovers all document files
   in the assets directory and builds samples with only multimodal input.
   No referenceResponse is included.

Each ground truth file (mode 1) must have a corresponding document file:
    <base-name>.png (or .jpg, .jpeg, .webp, .gif, .pdf — configurable via --doc-ext)

Usage:
    # With ground truth:
    python .kiro/skills/bedrock-advanced-prompt-optimization/scripts/build_multimodal_samples.py \
        --assets-dir assets/bank-checks \
        --bucket my-bucket \
        --s3-prefix prompt-optimization/my-job/images \
        --output prompt-optimization/samples.json \
        --region us-east-1

    # Without ground truth:
    python .kiro/skills/bedrock-advanced-prompt-optimization/scripts/build_multimodal_samples.py \
        --assets-dir assets/bank-checks \
        --no-ground-truth \
        --bucket my-bucket \
        --s3-prefix prompt-optimization/my-job/images \
        --output prompt-optimization/samples.json \
        --region us-east-1
"""

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UploadTask:
    """Represents a single file to upload and its associated metadata."""

    local_path: Path
    s3_key: str
    s3_uri: str
    gt_file: Path | None
    ground_truth: dict | None


def upload_to_s3(local_path: Path, bucket: str, key: str, region: str) -> tuple[bool, str]:
    """Upload a file to S3. Returns (success, error_message)."""
    s3_uri = f"s3://{bucket}/{key}"
    result = subprocess.run(
        ["aws", "s3", "cp", str(local_path), s3_uri, "--region", region],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()
    return True, ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Advanced Prompt Optimization samples JSON from ground truth + document files."
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        required=True,
        help="Directory containing ground truth JSON and document files.",
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="S3 bucket name for uploading documents.",
    )
    parser.add_argument(
        "--s3-prefix",
        default="prompt-optimization/documents",
        help="S3 key prefix for uploaded files (default: prompt-optimization/documents).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("prompt-optimization/samples.json"),
        help="Output samples JSON file path (default: prompt-optimization/samples.json).",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region for S3 uploads (default: us-east-1).",
    )
    parser.add_argument(
        "--doc-ext",
        nargs="+",
        default=[".png", ".jpg", ".jpeg", ".webp", ".gif"],
        help="Document file extension(s) to look for "
        "(default: .png .jpg .jpeg .webp .gif). "
        "Accepts multiple values, e.g. --doc-ext .png .tiff .pdf",
    )
    parser.add_argument(
        "--multimodal-name",
        default="document_image",
        help="Name for the multimodal variable in the sample (default: document_image).",
    )
    parser.add_argument(
        "--multimodal-type",
        choices=["IMAGE", "PDF"],
        default="IMAGE",
        help="Type of multimodal input (default: IMAGE).",
    )
    parser.add_argument(
        "--no-ground-truth",
        action="store_true",
        help="Build samples without ground truth. Discovers all document files "
        "in --assets-dir matching --doc-ext and creates samples with only "
        "multimodal input (no referenceResponse).",
    )
    parser.add_argument(
        "--gt-suffix",
        default="-ground_truth.json",
        help="Suffix for ground truth files (default: -ground_truth.json).",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip S3 upload (assume files are already uploaded).",
    )
    parser.add_argument(
        "--input-variables",
        type=Path,
        help="Optional JSON file with text input variables to include in every sample. "
        "Should be a dict of {variableName: value}.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=10,
        help="Number of parallel uploads (default: 10). Set to 1 for sequential.",
    )

    args = parser.parse_args()

    if not args.assets_dir.exists():
        print(f"ERROR: Assets directory not found: {args.assets_dir}", file=sys.stderr)
        sys.exit(1)

    # Load optional shared input variables
    shared_input_vars: dict = {}
    if args.input_variables:
        if not args.input_variables.exists():
            print(
                f"ERROR: Input variables file not found: {args.input_variables}",
                file=sys.stderr,
            )
            sys.exit(1)
        with open(args.input_variables) as f:
            shared_input_vars = json.load(f)
        if not isinstance(shared_input_vars, dict):
            print(
                "ERROR: --input-variables file must contain a JSON object.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Build list of upload tasks depending on mode
    upload_tasks: list[UploadTask] = []
    skipped: list[str] = []

    if args.no_ground_truth:
        # Discover all document files directly across all extensions
        doc_files: list[Path] = []
        for ext in args.doc_ext:
            doc_files.extend(args.assets_dir.glob(f"*{ext}"))
        doc_files = sorted(set(doc_files))

        if not doc_files:
            print(
                f"ERROR: No files matching {args.doc_ext} found in {args.assets_dir}.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"Found {len(doc_files)} document files in {args.assets_dir} (no ground truth mode)")

        for doc_file in doc_files:
            s3_key = f"{args.s3_prefix}/{doc_file.name}"
            s3_uri = f"s3://{args.bucket}/{s3_key}"

            upload_tasks.append(UploadTask(
                local_path=doc_file,
                s3_key=s3_key,
                s3_uri=s3_uri,
                gt_file=None,
                ground_truth=None,
            ))
    else:
        # Find all ground truth files and pair with documents
        gt_pattern = f"*{args.gt_suffix}"
        gt_files = sorted(args.assets_dir.glob(gt_pattern))

        if not gt_files:
            print(
                f"ERROR: No {gt_pattern} files found in {args.assets_dir}. "
                f"Use --no-ground-truth to build samples without ground truth.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"Found {len(gt_files)} ground truth files in {args.assets_dir}")

        for gt_file in gt_files:
            base_name = gt_file.name.replace(args.gt_suffix, "")

            # Try each extension in order to find the matching document
            doc_file: Path | None = None
            for ext in args.doc_ext:
                candidate = args.assets_dir / f"{base_name}{ext}"
                if candidate.exists():
                    doc_file = candidate
                    break

            if doc_file is None:
                skipped.append(gt_file.name)
                print(
                    f"  WARNING: No document matching {args.doc_ext} found for "
                    f"{gt_file.name}, skipping."
                )
                continue

            s3_key = f"{args.s3_prefix}/{doc_file.name}"
            s3_uri = f"s3://{args.bucket}/{s3_key}"

            with open(gt_file) as f:
                ground_truth = json.load(f)

            upload_tasks.append(UploadTask(
                local_path=doc_file,
                s3_key=s3_key,
                s3_uri=s3_uri,
                gt_file=gt_file,
                ground_truth=ground_truth,
            ))

    # Upload files (parallel or skip)
    upload_failures: list[str] = []
    successful_tasks: list[UploadTask] = []

    if args.skip_upload:
        print(f"  Skipping upload — assuming {len(upload_tasks)} files already in S3.")
        successful_tasks = upload_tasks
    else:
        print(f"  Uploading {len(upload_tasks)} files ({args.parallel} parallel)...")

        def do_upload(task: UploadTask) -> tuple[UploadTask, bool, str]:
            success, error = upload_to_s3(
                task.local_path, args.bucket, task.s3_key, args.region
            )
            return task, success, error

        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = {executor.submit(do_upload, task): task for task in upload_tasks}
            completed = 0
            for future in as_completed(futures):
                task, success, error = future.result()
                completed += 1
                if success:
                    successful_tasks.append(task)
                    print(f"    [{completed}/{len(upload_tasks)}] ✓ {task.local_path.name}")
                else:
                    upload_failures.append(task.local_path.name)
                    print(
                        f"    [{completed}/{len(upload_tasks)}] ✗ {task.local_path.name}: {error}",
                        file=sys.stderr,
                    )

    # Build samples from successful uploads
    samples = []
    for task in successful_tasks:
        sample: dict = {
            "inputVariablesMultimodal": [
                {args.multimodal_name: {"type": args.multimodal_type, "s3Uri": task.s3_uri}}
            ],
        }
        if task.ground_truth is not None:
            sample["referenceResponse"] = json.dumps(task.ground_truth)
        if shared_input_vars:
            sample["inputVariables"] = [
                {k: v} for k, v in shared_input_vars.items()
            ]
        samples.append(sample)

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Write samples JSON
    with open(args.output, "w") as f:
        json.dump(samples, f, indent=2)

    print(f"\nDone! Created {args.output} with {len(samples)} samples.")
    if skipped:
        print(f"  Skipped (no matching document): {len(skipped)}")
    if upload_failures:
        print(f"  Upload failures: {upload_failures}")


if __name__ == "__main__":
    main()
