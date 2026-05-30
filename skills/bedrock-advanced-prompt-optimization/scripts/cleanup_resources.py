"""Delete AWS resources created during an Advanced Prompt Optimization workflow.

Reads advpo-resources.json and deletes each tracked resource,
prompting for confirmation by resource type.

Usage:
    python .kiro/skills/bedrock-advpo/scripts/cleanup_resources.py \
        --resources advpo-resources.json \
        --region us-east-1

    # Skip confirmation prompts:
    python .kiro/skills/bedrock-advpo/scripts/cleanup_resources.py \
        --resources advpo-resources.json \
        --region us-east-1 \
        --yes

    # Delete only specific resource types:
    python .kiro/skills/bedrock-advpo/scripts/cleanup_resources.py \
        --resources advpo-resources.json \
        --region us-east-1 \
        --types lambda iam s3
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


RESOURCE_TYPES = ["lambda", "iam_role", "s3", "advpo_job"]


def delete_lambda(arn: str, region: str) -> bool:
    """Delete a Lambda function."""
    function_name = arn.split(":")[-1]
    result = subprocess.run(
        ["aws", "lambda", "delete-function",
         "--function-name", function_name,
         "--region", region],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def delete_iam_role(arn: str, region: str) -> bool:
    """Detach policies and delete an IAM role."""
    role_name = arn.split("/")[-1]

    # List and detach managed policies
    result = subprocess.run(
        ["aws", "iam", "list-attached-role-policies",
         "--role-name", role_name, "--output", "json"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        policies = json.loads(result.stdout).get("AttachedPolicies", [])
        for policy in policies:
            subprocess.run(
                ["aws", "iam", "detach-role-policy",
                 "--role-name", role_name,
                 "--policy-arn", policy["PolicyArn"]],
                capture_output=True, text=True,
            )

    # Delete the role
    result = subprocess.run(
        ["aws", "iam", "delete-role", "--role-name", role_name],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def delete_s3_object(uri: str, region: str) -> bool:
    """Delete an S3 object."""
    result = subprocess.run(
        ["aws", "s3", "rm", uri, "--region", region],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def delete_advpo_job(arn: str, region: str) -> bool:
    """Delete an Advanced Prompt Optimization job."""
    result = subprocess.run(
        ["aws", "bedrock", "delete-advanced-prompt-optimization-job",
         "--advanced-prompt-optimization-job-arn", arn,
         "--region", region],
        capture_output=True, text=True,
    )
    return result.returncode == 0


DELETE_HANDLERS = {
    "lambda": delete_lambda,
    "iam_role": delete_iam_role,
    "s3": delete_s3_object,
    "advpo_job": delete_advpo_job,
}

TYPE_LABELS = {
    "lambda": "Lambda Functions",
    "iam_role": "IAM Roles",
    "s3": "S3 Objects",
    "advpo_job": "Advanced Prompt Optimization Jobs",
}


def confirm(prompt: str) -> bool:
    """Ask for user confirmation."""
    response = input(f"{prompt} [y/N]: ").strip().lower()
    return response in ("y", "yes")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete AWS resources tracked in advpo-resources.json."
    )
    parser.add_argument(
        "--resources",
        type=Path,
        default=Path("advpo-resources.json"),
        help="Path to the resources JSON file (default: advpo-resources.json).",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1).",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts and delete all resources.",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        choices=RESOURCE_TYPES,
        help="Only delete specific resource types.",
    )

    args = parser.parse_args()

    if not args.resources.exists():
        print(f"ERROR: Resources file not found: {args.resources}", file=sys.stderr)
        sys.exit(1)

    with open(args.resources) as f:
        resources = json.load(f)

    types_to_delete = args.types or RESOURCE_TYPES
    deleted = []
    failed = []

    for resource_type in types_to_delete:
        items = resources.get(resource_type, [])
        if not items:
            continue

        label = TYPE_LABELS.get(resource_type, resource_type)
        print(f"\n{label} ({len(items)}):")
        for item in items:
            print(f"  - {item['id']}")

        if not args.yes:
            if not confirm(f"Delete these {len(items)} {label.lower()}?"):
                print("  Skipped.")
                continue

        handler = DELETE_HANDLERS[resource_type]
        for item in items:
            resource_id = item["id"]
            print(f"  Deleting {resource_id}...", end=" ")
            if handler(resource_id, args.region):
                print("✓")
                deleted.append(resource_id)
            else:
                print("FAILED")
                failed.append(resource_id)

    # Update the resources file to remove deleted items
    for resource_type in types_to_delete:
        items = resources.get(resource_type, [])
        resources[resource_type] = [
            item for item in items if item["id"] not in deleted
        ]

    # Remove empty lists
    resources = {k: v for k, v in resources.items() if v}

    if resources:
        with open(args.resources, "w") as f:
            json.dump(resources, f, indent=2)
        print(f"\nUpdated {args.resources} with remaining resources.")
    else:
        args.resources.unlink()
        print(f"\nAll resources deleted. Removed {args.resources}.")

    print(f"\nSummary: {len(deleted)} deleted, {len(failed)} failed.")
    if failed:
        print("Failed resources:")
        for r in failed:
            print(f"  - {r}")
        sys.exit(1)


if __name__ == "__main__":
    main()
