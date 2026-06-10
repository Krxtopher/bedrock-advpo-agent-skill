"""Parse and display results from a Bedrock Advanced Prompt Optimization job.

Downloads the results JSONL from S3 and presents optimized prompts,
evaluation scores, latency, and cost estimates.
"""

import argparse
import json
import sys
from io import BytesIO

import boto3


def get_results_key(job_arn: str, output_s3_uri: str) -> tuple[str, str]:
    """Derive the S3 bucket and key for the results file.

    Returns (bucket, key) tuple.
    """
    job_id = job_arn.split("/")[-1]

    # Parse the output S3 URI
    if not output_s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {output_s3_uri}")

    path = output_s3_uri[5:]  # Remove 's3://'
    parts = path.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""

    # Ensure prefix ends with /
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    key = f"{prefix}{job_id}/advanced_prompt_optimization_results.jsonl"
    return bucket, key


def download_results(
    bucket: str,
    key: str,
    region: str,
    profile: str | None = None,
) -> str:
    """Download the results JSONL file from S3."""
    session_kwargs: dict = {}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    s3 = session.client("s3", region_name=region)

    buffer = BytesIO()
    s3.download_fileobj(bucket, key, buffer)
    return buffer.getvalue().decode("utf-8")


def format_results(content: str, verbose: bool = False) -> str:
    """Format the results JSONL content for display."""
    lines = []

    for line_num, raw_line in enumerate(content.strip().split("\n"), 1):
        if not raw_line.strip():
            continue

        result = json.loads(raw_line)
        template_id = result.get("promptTemplateId", f"template-{line_num}")

        lines.append(f"{'=' * 70}")
        lines.append(f"Template: {template_id}")
        lines.append(f"{'=' * 70}")

        optimizations = result.get("promptOptimizationResults", [])
        if not optimizations:
            lines.append("  No optimization results available.")
            lines.append("")
            continue

        for opt in optimizations:
            model_id = opt.get("modelId", "unknown")
            status = opt.get("status", "unknown")

            lines.append(f"\n  Model: {model_id}")
            lines.append(f"  Status: {status}")

            # Score summary — show aggregate improvement first
            dataset = opt.get("dataset", [])
            if dataset:
                original_scores = []
                optimized_scores = []
                for sample in dataset:
                    orig_details = sample.get("originalPromptDetails", {})
                    opt_details = sample.get("optimizedPromptDetails", {})
                    orig_metrics = orig_details.get("originalPromptMetrics", {})
                    opt_metrics = opt_details.get("optimizedPromptMetrics", {})
                    if "score" in orig_metrics:
                        original_scores.append(orig_metrics["score"])
                    if "score" in opt_metrics:
                        optimized_scores.append(opt_metrics["score"])

                if original_scores and optimized_scores:
                    orig_avg = sum(original_scores) / len(original_scores)
                    opt_avg = sum(optimized_scores) / len(optimized_scores)
                    improvement = opt_avg - orig_avg
                    sign = "+" if improvement >= 0 else ""

                    lines.append(f"\n  Score Summary ({len(original_scores)} samples):")
                    lines.append(f"    Original prompt avg score:  {orig_avg:.4f}")
                    lines.append(f"    Optimized prompt avg score: {opt_avg:.4f}")
                    lines.append(f"    Improvement:                {sign}{improvement:.4f} ({sign}{improvement * 100:.1f}%)")

            # Optimized prompt
            optimized = opt.get("optimizedPromptTemplate", "")
            if optimized:
                lines.append(f"\n  Optimized Prompt Template:")
                lines.append(f"  {'-' * 40}")
                # Indent the prompt for readability
                for prompt_line in optimized.split("\n"):
                    lines.append(f"    {prompt_line}")
                lines.append(f"  {'-' * 40}")

            # Latency
            if opt.get("latency"):
                latency = opt["latency"]
                lines.append(f"\n  Latency (TTFT): {latency}")

            # Cost
            if opt.get("costEstimate"):
                cost = opt["costEstimate"]
                lines.append(f"  Cost Estimate: {cost}")

            # Evaluation scores
            if opt.get("evaluationScores"):
                lines.append(f"\n  Evaluation Scores:")
                scores = opt["evaluationScores"]
                if isinstance(scores, list):
                    for i, score in enumerate(scores):
                        if isinstance(score, dict):
                            for k, v in score.items():
                                lines.append(f"    Sample {i + 1} - {k}: {v}")
                        else:
                            lines.append(f"    Sample {i + 1}: {score}")
                elif isinstance(scores, dict):
                    for k, v in scores.items():
                        lines.append(f"    {k}: {v}")

            # Verbose: show all fields
            if verbose:
                lines.append(f"\n  Full response:")
                lines.append(
                    json.dumps(opt, indent=4, default=str)
                )

            lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse and display Advanced Prompt Optimization job results."
    )
    parser.add_argument(
        "--job-arn",
        required=True,
        help="The job ARN (used to derive the results file path).",
    )
    parser.add_argument(
        "--output-s3-uri",
        required=True,
        help="The output S3 URI prefix used when creating the job.",
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
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full raw JSON for each result.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output raw JSONL content.",
    )
    parser.add_argument(
        "--save",
        type=str,
        help="Save the raw results JSONL to this local file path.",
    )

    args = parser.parse_args()

    try:
        bucket, key = get_results_key(args.job_arn, args.output_s3_uri)
        print(f"Downloading results from s3://{bucket}/{key} ...", file=sys.stderr)

        content = download_results(bucket, key, args.region, args.profile)

        if args.save:
            with open(args.save, "w") as f:
                f.write(content)
            print(f"Saved raw results to: {args.save}", file=sys.stderr)

        if args.json_output:
            print(content)
        else:
            print(format_results(content, verbose=args.verbose))

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
