"""Deploy a Lambda evaluator function for AdvPO.

Handles the full deployment lifecycle:
1. Create IAM role with trust policy for Lambda and Bedrock
2. Attach AWSLambdaBasicExecutionRole policy
3. Wait for IAM role propagation
4. Zip and deploy the Lambda function
5. Add resource-based permission for Bedrock service
6. Add resource-based permission for the caller's IAM role
7. Verify the function is active
8. Tag all created resources

Each step reports clearly on success or failure. On failure, the script
exits with a non-zero code and reports which step failed and why, leaving
partial resources in place so the agent can diagnose and retry.

Usage:
    python .kiro/skills/bedrock-advpo/scripts/deploy_evaluator.py \
        --function-name advpo-check-evaluator \
        --source prompt-optimization/evaluator/lambda_function.py \
        --region us-east-1

    # With a specific profile and tags:
    python .kiro/skills/bedrock-advpo/scripts/deploy_evaluator.py \
        --function-name advpo-check-evaluator \
        --source prompt-optimization/evaluator/lambda_function.py \
        --region us-east-1 \
        --profile admin-933 \
        --tags owner=schultkr project=check-extraction

    # Custom role name:
    python .kiro/skills/bedrock-advpo/scripts/deploy_evaluator.py \
        --function-name advpo-check-evaluator \
        --source prompt-optimization/evaluator/lambda_function.py \
        --region us-east-1 \
        --role-name my-custom-evaluator-role

    # Grant invoke access to a different role (e.g., the role that creates AdvPO jobs):
    python .kiro/skills/bedrock-advpo/scripts/deploy_evaluator.py \
        --function-name advpo-check-evaluator \
        --source prompt-optimization/evaluator/lambda_function.py \
        --region us-east-1 \
        --profile admin-933 \
        --invoker-role arn:aws:iam::905418197933:role/agi-solutions-builder
"""

import argparse
import json
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


TRUST_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": [
                    "lambda.amazonaws.com",
                    "bedrock.amazonaws.com",
                ]
            },
            "Action": "sts:AssumeRole",
        }
    ],
})

LAMBDA_BASIC_EXECUTION_POLICY = (
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
)


def step(number: int, total: int, description: str) -> None:
    """Print a step header."""
    print(f"\n[Step {number}/{total}] {description}")


def get_caller_role_arn(session: boto3.Session) -> str:
    """Get the caller's IAM role ARN from STS."""
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    caller_arn = identity["Arn"]

    # Convert assumed-role ARN to role ARN
    # arn:aws:sts::ACCOUNT:assumed-role/ROLE/SESSION → arn:aws:iam::ACCOUNT:role/ROLE
    if ":assumed-role/" in caller_arn:
        parts = caller_arn.split(":")
        account = parts[4]
        role_name = parts[5].split("/")[1]
        return f"arn:aws:iam::{account}:role/{role_name}"

    return caller_arn


def create_iam_role(
    iam_client,
    role_name: str,
    tags: list[dict[str, str]] | None = None,
) -> str:
    """Create the IAM role. Returns the role ARN."""
    try:
        kwargs: dict = {
            "RoleName": role_name,
            "AssumeRolePolicyDocument": TRUST_POLICY,
            "Description": "Execution role for AdvPO Lambda evaluator",
        }
        if tags:
            kwargs["Tags"] = [{"Key": k, "Value": v} for k, v in tags]

        response = iam_client.create_role(**kwargs)
        role_arn = response["Role"]["Arn"]
        print(f"  Created role: {role_arn}")
        return role_arn

    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            # Role already exists — get its ARN
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
            print(f"  Role already exists: {role_arn}")
            return role_arn
        raise


def attach_execution_policy(iam_client, role_name: str) -> None:
    """Attach the basic Lambda execution policy."""
    try:
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=LAMBDA_BASIC_EXECUTION_POLICY,
        )
        print(f"  Attached AWSLambdaBasicExecutionRole")
    except ClientError as e:
        if e.response["Error"]["Code"] == "PolicyNotAttachable":
            raise
        # If already attached, that's fine
        print(f"  Policy already attached")


def wait_for_role_propagation(seconds: int = 10) -> None:
    """Wait for IAM role to propagate across AWS."""
    print(f"  Waiting {seconds}s for IAM role propagation...")
    time.sleep(seconds)
    print(f"  Done.")


def zip_function(source_path: Path) -> Path:
    """Zip the Lambda function source file. Returns path to zip."""
    zip_path = Path(tempfile.mktemp(suffix=".zip"))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(source_path, "lambda_function.py")
    print(f"  Zipped {source_path} → {zip_path} ({zip_path.stat().st_size} bytes)")
    return zip_path


def create_lambda_function(
    lambda_client,
    function_name: str,
    role_arn: str,
    zip_path: Path,
    tags: dict[str, str] | None = None,
) -> str:
    """Create the Lambda function. Returns the function ARN."""
    zip_bytes = zip_path.read_bytes()

    try:
        kwargs: dict = {
            "FunctionName": function_name,
            "Runtime": "python3.12",
            "Handler": "lambda_function.lambda_handler",
            "Role": role_arn,
            "Code": {"ZipFile": zip_bytes},
            "Timeout": 900,
            "Description": "AdvPO custom evaluator function",
        }
        if tags:
            kwargs["Tags"] = tags

        response = lambda_client.create_function(**kwargs)
        function_arn = response["FunctionArn"]
        print(f"  Created function: {function_arn}")
        return function_arn

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            # Function already exists — update its code instead
            print(f"  Function already exists. Updating code...")
            lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_bytes,
            )
            response = lambda_client.get_function(FunctionName=function_name)
            function_arn = response["Configuration"]["FunctionArn"]
            print(f"  Updated function: {function_arn}")
            return function_arn
        raise


def add_permission(
    lambda_client,
    function_name: str,
    statement_id: str,
    principal: str,
) -> None:
    """Add a resource-based permission to the Lambda function."""
    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal=principal,
        )
        print(f"  Added permission: {statement_id} → {principal}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            print(f"  Permission already exists: {statement_id}")
        else:
            raise


def wait_for_function_active(
    lambda_client,
    function_name: str,
    max_wait: int = 30,
) -> None:
    """Wait for the Lambda function to become Active."""
    print(f"  Waiting for function to become Active...")
    start = time.time()
    while time.time() - start < max_wait:
        response = lambda_client.get_function(FunctionName=function_name)
        state = response["Configuration"]["State"]
        if state == "Active":
            print(f"  Function is Active.")
            return
        if state == "Failed":
            reason = response["Configuration"].get("StateReason", "unknown")
            raise RuntimeError(
                f"Function entered Failed state: {reason}"
            )
        time.sleep(2)

    raise RuntimeError(
        f"Function did not become Active within {max_wait}s "
        f"(current state: {state})"
    )


def parse_tags(tag_strings: list[str] | None) -> list[dict[str, str]] | None:
    """Parse key=value tag strings into a list of (key, value) tuples."""
    if not tag_strings:
        return None
    tags = []
    for tag_str in tag_strings:
        if "=" not in tag_str:
            print(
                f"ERROR: Invalid tag format '{tag_str}'. Use key=value.",
                file=sys.stderr,
            )
            sys.exit(1)
        key, value = tag_str.split("=", 1)
        tags.append((key, value))
    return tags


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy a Lambda evaluator function for AdvPO."
    )
    parser.add_argument(
        "--function-name",
        required=True,
        help="Name for the Lambda function.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the Lambda function source file (lambda_function.py).",
    )
    parser.add_argument(
        "--region",
        required=True,
        help="AWS region for the Lambda function.",
    )
    parser.add_argument(
        "--role-name",
        help="IAM role name (default: <function-name>-role).",
    )
    parser.add_argument(
        "--profile",
        help="AWS profile name.",
    )
    parser.add_argument(
        "--invoker-role",
        help=(
            "ARN of an additional IAM role to grant lambda:InvokeFunction. "
            "Use when the role that creates AdvPO jobs differs from the role "
            "deploying the function (e.g., deploy with admin, run jobs with "
            "a scoped-down role)."
        ),
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        metavar="KEY=VALUE",
        help="Tags to apply to created resources (e.g., --tags owner=schultkr).",
    )

    args = parser.parse_args()

    if not args.source.exists():
        print(f"ERROR: Source file not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    role_name = args.role_name or f"{args.function_name}-role"
    tags = parse_tags(args.tags)

    # Create session
    session_kwargs: dict = {}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs, region_name=args.region)

    iam_client = session.client("iam")
    lambda_client = session.client("lambda", region_name=args.region)

    print(f"Deploying Lambda evaluator: {args.function_name}")
    print(f"  Source: {args.source}")
    print(f"  Region: {args.region}")
    print(f"  Role: {role_name}")
    if args.profile:
        print(f"  Profile: {args.profile}")

    # Get caller role for permission grant
    caller_role_arn = get_caller_role_arn(session)
    print(f"  Caller role: {caller_role_arn}")

    try:
        total_steps = 8 if args.invoker_role else 7

        # Step 1: Create IAM role
        step(1, total_steps, "Creating IAM role")
        iam_tags = [(k, v) for k, v in tags] if tags else None
        role_arn = create_iam_role(iam_client, role_name, iam_tags)

        # Step 2: Attach execution policy
        step(2, total_steps, "Attaching execution policy")
        attach_execution_policy(iam_client, role_name)

        # Step 3: Wait for propagation
        step(3, total_steps, "Waiting for IAM propagation")
        wait_for_role_propagation(10)

        # Step 4: Deploy Lambda function
        step(4, total_steps, "Deploying Lambda function")
        zip_path = zip_function(args.source)
        lambda_tags = {k: v for k, v in tags} if tags else None
        try:
            function_arn = create_lambda_function(
                lambda_client, args.function_name, role_arn, zip_path, lambda_tags
            )
        finally:
            zip_path.unlink(missing_ok=True)

        # Step 5: Add Bedrock service permission
        step(5, total_steps, "Adding Bedrock invoke permission")
        add_permission(
            lambda_client,
            args.function_name,
            "AllowBedrockInvoke",
            "bedrock.amazonaws.com",
        )

        # Step 6: Add caller role permission
        step(6, total_steps, "Adding caller role invoke permission")
        add_permission(
            lambda_client,
            args.function_name,
            "AllowCallerInvoke",
            caller_role_arn,
        )

        # Step 7 (optional): Add invoker role permission
        next_step = 7
        if args.invoker_role:
            step(7, total_steps, "Adding invoker role invoke permission")
            add_permission(
                lambda_client,
                args.function_name,
                "AllowInvokerRoleInvoke",
                args.invoker_role,
            )
            next_step = 8

        # Final step: Verify function is active
        step(next_step, total_steps, "Verifying function is active")
        wait_for_function_active(lambda_client, args.function_name)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        print(
            f"\nFAILED: {error_code} — {error_msg}",
            file=sys.stderr,
        )
        print(
            f"\nPartial resources may exist. Check and retry or clean up manually.",
            file=sys.stderr,
        )
        sys.exit(1)
    except RuntimeError as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        sys.exit(1)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Deployment complete!")
    print(f"  Function ARN: {function_arn}")
    print(f"  Role ARN:     {role_arn}")
    print(f"{'=' * 60}")

    # Output JSON for easy parsing by the agent
    output = {
        "function_arn": function_arn,
        "role_arn": role_arn,
        "function_name": args.function_name,
        "role_name": role_name,
        "region": args.region,
    }
    print(f"\n{json.dumps(output)}")


if __name__ == "__main__":
    main()
