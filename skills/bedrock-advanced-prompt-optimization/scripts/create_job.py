"""Create a Bedrock Advanced Prompt Optimization job.

This script creates an AdvPO job with the specified configuration and returns
the job ARN for tracking. Includes a pre-flight check to verify model access.

A short hex suffix is automatically appended to the job name to prevent naming
conflicts on retries or repeated runs.
"""

import argparse
import hashlib
import json
import sys
import time

import boto3
from botocore.exceptions import ClientError


def generate_job_suffix() -> str:
    """Generate a short unique hex suffix from the current timestamp."""
    timestamp = str(time.time_ns())
    return hashlib.sha256(timestamp.encode()).hexdigest()[:4]


def check_model_access(
    client,
    model_ids: list[str],
    region: str,
) -> list[str]:
    """Check that all target models are accessible. Returns list of inaccessible models."""
    inaccessible = []

    for model_id in model_ids:
        # Cross-region inference profile IDs (e.g. us.anthropic.claude-...) won't
        # resolve via GetFoundationModel. Strip the region prefix to check the base model.
        base_model_id = model_id
        if "." in model_id:
            parts = model_id.split(".", 1)
            # If first part looks like a region prefix (2-3 chars), strip it
            if len(parts[0]) <= 3:
                base_model_id = parts[1]

        try:
            response = client.get_foundation_model(modelIdentifier=base_model_id)
            status = response.get("modelDetails", {}).get("modelLifecycle", {}).get(
                "status", "UNKNOWN"
            )
            if status == "LEGACY":
                print(
                    f"  WARNING: Model {model_id} has LEGACY status and may be "
                    "deprecated soon.",
                    file=sys.stderr,
                )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("ResourceNotFoundException", "ValidationException"):
                inaccessible.append(model_id)
            else:
                # Other errors (permissions, throttling) — warn but don't block
                print(
                    f"  WARNING: Could not verify model {model_id}: {e}",
                    file=sys.stderr,
                )

    return inaccessible


def create_job(
    job_name: str,
    input_s3_uri: str,
    output_s3_uri: str,
    model_ids: list[str],
    region: str,
    profile: str | None = None,
    description: str | None = None,
    kms_key_id: str | None = None,
    skip_preflight: bool = False,
    tags: list[dict[str, str]] | None = None,
) -> dict:
    """Create an Advanced Prompt Optimization job."""
    session_kwargs: dict = {}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    client = session.client("bedrock", region_name=region)

    # Pre-flight model access check
    if not skip_preflight:
        print("Checking model access...", file=sys.stderr)
        inaccessible = check_model_access(client, model_ids, region)
        if inaccessible:
            print(
                f"ERROR: The following models are not accessible in {region}:\n"
                f"  {inaccessible}\n"
                "Ensure model access is enabled in the Bedrock console.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("  All models accessible.", file=sys.stderr)

    model_configurations = [{"modelId": model_id} for model_id in model_ids]

    kwargs: dict = {
        "jobName": job_name,
        "modelConfigurations": model_configurations,
        "inputConfig": {"s3Uri": input_s3_uri},
        "outputConfig": {"s3Uri": output_s3_uri},
    }

    if description:
        kwargs["jobDescription"] = description

    if kms_key_id:
        kwargs["encryptionKeyArn"] = kms_key_id

    if tags:
        kwargs["tags"] = tags

    response = client.create_advanced_prompt_optimization_job(**kwargs)
    return response


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a Bedrock Advanced Prompt Optimization job."
    )
    parser.add_argument(
        "--job-name",
        required=True,
        help="Name for the optimization job.",
    )
    parser.add_argument(
        "--input-s3-uri",
        required=True,
        help="S3 URI of the input JSONL dataset (e.g., s3://bucket/path/dataset.jsonl).",
    )
    parser.add_argument(
        "--output-s3-uri",
        required=True,
        help="S3 URI prefix for output results (e.g., s3://bucket/output/).",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        required=True,
        help="Target model IDs (up to 5). Use cross-region inference profile IDs "
        "like 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'.",
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
        "--description",
        help="Optional job description.",
    )
    parser.add_argument(
        "--kms-key-id",
        help="Optional KMS key ARN for output encryption.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip the pre-flight model access check.",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        metavar="KEY=VALUE",
        help="Tags to apply to the job (e.g., --tags owner=schultkr project=check-extraction).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output raw JSON response.",
    )

    args = parser.parse_args()

    if len(args.models) > 5:
        print("ERROR: Maximum 5 models per job.", file=sys.stderr)
        sys.exit(1)

    # Append a unique suffix to prevent naming conflicts on retries
    suffix = generate_job_suffix()
    job_name = f"{args.job_name}-{suffix}"

    # Parse tags from key=value format
    tags: list[dict[str, str]] | None = None
    if args.tags:
        tags = []
        for tag_str in args.tags:
            if "=" not in tag_str:
                print(
                    f"ERROR: Invalid tag format '{tag_str}'. Use key=value.",
                    file=sys.stderr,
                )
                sys.exit(1)
            key, value = tag_str.split("=", 1)
            tags.append({"key": key, "value": value})

    try:
        response = create_job(
            job_name=job_name,
            input_s3_uri=args.input_s3_uri,
            output_s3_uri=args.output_s3_uri,
            model_ids=args.models,
            region=args.region,
            profile=args.profile,
            description=args.description,
            kms_key_id=args.kms_key_id,
            skip_preflight=args.skip_preflight,
            tags=tags,
        )
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json_output:
        # Remove ResponseMetadata for cleaner output
        response.pop("ResponseMetadata", None)
        print(json.dumps(response, indent=2, default=str))
    else:
        job_arn = response["jobArn"]
        print(f"Job created successfully!")
        print(f"  ARN: {job_arn}")
        print(f"  Name: {job_name}")
        print(f"  Models: {args.models}")
        print(f"  Input: {args.input_s3_uri}")
        print(f"  Output: {args.output_s3_uri}")
        print(f"  Region: {args.region}")
        print()
        print("Monitor with:")
        print(
            f"  python .kiro/skills/bedrock-advpo/scripts/manage_job.py status "
            f'--job-arn "{job_arn}" --region {args.region}'
        )


if __name__ == "__main__":
    main()
