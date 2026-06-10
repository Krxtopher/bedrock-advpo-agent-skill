"""Extract the optimized prompt from Advanced Prompt Optimization results and save as a clean file.

Reads the results JSONL (local or from S3), extracts the optimized prompt
template for a given template ID and model, and writes it to a file ready
for use.

Usage:
    # From local results file:
    python .kiro/skills/bedrock-advanced-prompt-optimization/scripts/extract_prompt.py \
        --results prompt-optimization/results.jsonl \
        --output prompts/my-prompt-optimized.md

    # From S3 (using job ARN):
    python .kiro/skills/bedrock-advanced-prompt-optimization/scripts/extract_prompt.py \
        --job-arn "arn:aws:bedrock:us-east-1:123456789012:advanced-prompt-optimization-job/abc123" \
        --output-s3-uri "s3://my-bucket/prompt-optimization/my-job/output/" \
        --output prompts/my-prompt-optimized.md \
        --region us-east-1

    # Extract a specific template/model when results contain multiple:
    python .kiro/skills/bedrock-advanced-prompt-optimization/scripts/extract_prompt.py \
        --results prompt-optimization/results.jsonl \
        --output prompts/my-prompt-optimized.md \
        --template-id "my-template-v1" \
        --model "us.amazon.nova-2-lite-v1:0"
"""

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

import boto3


def load_results_from_file(path: Path) -> str:
    """Load results JSONL from a local file."""
    if not path.exists():
        print(f"ERROR: Results file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text()


def load_results_from_s3(
    job_arn: str,
    output_s3_uri: str,
    region: str,
    profile: str | None = None,
) -> str:
    """Download results JSONL from S3."""
    job_id = job_arn.split("/")[-1]

    if not output_s3_uri.startswith("s3://"):
        print(f"ERROR: Invalid S3 URI: {output_s3_uri}", file=sys.stderr)
        sys.exit(1)

    path = output_s3_uri[5:]
    parts = path.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""

    if prefix and not prefix.endswith("/"):
        prefix += "/"

    key = f"{prefix}{job_id}/advanced_prompt_optimization_results.jsonl"

    session_kwargs: dict = {}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    s3 = session.client("s3", region_name=region)

    print(f"Downloading results from s3://{bucket}/{key} ...", file=sys.stderr)
    buffer = BytesIO()
    s3.download_fileobj(bucket, key, buffer)
    return buffer.getvalue().decode("utf-8")


def extract_optimized_prompt(
    content: str,
    template_id: str | None = None,
    model_id: str | None = None,
) -> str:
    """Extract the optimized prompt template from results JSONL.

    If template_id or model_id are not specified, uses the first available.
    """
    records = []
    for raw_line in content.strip().split("\n"):
        if raw_line.strip():
            records.append(json.loads(raw_line))

    if not records:
        print("ERROR: No results found in the file.", file=sys.stderr)
        sys.exit(1)

    # Find the matching template
    target_record = None
    if template_id:
        for record in records:
            if record.get("promptTemplateId") == template_id:
                target_record = record
                break
        if not target_record:
            available = [r.get("promptTemplateId", "?") for r in records]
            print(
                f"ERROR: Template '{template_id}' not found. "
                f"Available: {available}",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        target_record = records[0]
        if len(records) > 1:
            print(
                f"Multiple templates found. Using first: "
                f"'{target_record.get('promptTemplateId', '?')}'. "
                f"Use --template-id to select a specific one.",
                file=sys.stderr,
            )

    # Find the matching model optimization
    optimizations = target_record.get("promptOptimizationResults", [])
    if not optimizations:
        print("ERROR: No optimization results in this template.", file=sys.stderr)
        sys.exit(1)

    target_opt = None
    if model_id:
        for opt in optimizations:
            if opt.get("modelId") == model_id:
                target_opt = opt
                break
        if not target_opt:
            available = [o.get("modelId", "?") for o in optimizations]
            print(
                f"ERROR: Model '{model_id}' not found. "
                f"Available: {available}",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        target_opt = optimizations[0]
        if len(optimizations) > 1:
            print(
                f"Multiple models found. Using first: "
                f"'{target_opt.get('modelId', '?')}'. "
                f"Use --model to select a specific one.",
                file=sys.stderr,
            )

    # Check status
    status = target_opt.get("status", "UNKNOWN")
    if status != "SUCCESS":
        print(
            f"WARNING: Optimization status is '{status}', not SUCCESS.",
            file=sys.stderr,
        )

    optimized_template = target_opt.get("optimizedPromptTemplate", "")
    if not optimized_template:
        print("ERROR: No optimized prompt template found.", file=sys.stderr)
        sys.exit(1)

    # Convert Advanced Prompt Optimization escaped braces back to normal braces
    # Advanced Prompt Optimization uses {{ and }} to escape literal braces in the template
    optimized_template = optimized_template.replace("{{", "{").replace("}}", "}")

    return optimized_template


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract the optimized prompt from Advanced Prompt Optimization results."
    )

    # Source: local file or S3
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--results",
        type=Path,
        help="Path to local results JSONL file.",
    )
    source_group.add_argument(
        "--job-arn",
        help="Job ARN (downloads results from S3).",
    )

    parser.add_argument(
        "--output-s3-uri",
        help="Output S3 URI prefix (required with --job-arn).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file path for the extracted prompt.",
    )
    parser.add_argument(
        "--template-id",
        help="Template ID to extract (default: first template in results).",
    )
    parser.add_argument(
        "--model",
        help="Model ID to extract (default: first model in results).",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1).",
    )
    parser.add_argument(
        "--profile",
        help="AWS profile name.",
    )

    args = parser.parse_args()

    if args.job_arn and not args.output_s3_uri:
        print(
            "ERROR: --output-s3-uri is required when using --job-arn.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load results
    if args.results:
        content = load_results_from_file(args.results)
    else:
        content = load_results_from_s3(
            args.job_arn, args.output_s3_uri, args.region, args.profile
        )

    # Extract the prompt
    optimized_prompt = extract_optimized_prompt(
        content,
        template_id=args.template_id,
        model_id=args.model,
    )

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(optimized_prompt + "\n")

    print(f"Extracted optimized prompt to: {args.output}")


if __name__ == "__main__":
    main()
