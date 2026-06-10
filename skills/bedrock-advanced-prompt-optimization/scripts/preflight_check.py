"""Pre-flight permissions check for the Advanced Prompt Optimization workflow.

Validates that the caller has the necessary AWS permissions before starting
the optimization workflow. Reports missing permissions and suggests which
operations require an elevated role.

Usage:
    python .kiro/skills/bedrock-advanced-prompt-optimization/scripts/preflight_check.py \
        --bucket my-bucket \
        --s3-prefix prompt-optimization/my-job/input \
        --region us-east-1

    # Test a specific profile:
    python .kiro/skills/bedrock-advanced-prompt-optimization/scripts/preflight_check.py \
        --bucket my-bucket \
        --s3-prefix prompt-optimization/my-job/input \
        --region us-east-1 \
        --profile admin-933
"""

import argparse
import json
import sys
from dataclasses import dataclass, field

import boto3
from botocore.exceptions import ClientError


@dataclass
class CheckResult:
    """Result of a single permission check."""

    service: str
    action: str
    status: str  # "allowed", "denied", "error"
    message: str = ""
    requires_admin: bool = False


@dataclass
class PreflightReport:
    """Aggregated results of all permission checks."""

    identity_arn: str = ""
    account_id: str = ""
    results: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.status == "allowed" for r in self.results)

    @property
    def denied_results(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == "denied"]

    @property
    def admin_required(self) -> list[CheckResult]:
        return [r for r in self.denied_results if r.requires_admin]


def check_identity(session: boto3.Session) -> tuple[str, str]:
    """Get the current caller identity."""
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    return identity["Arn"], identity["Account"]


def check_s3_put(session: boto3.Session, bucket: str, prefix: str, region: str) -> CheckResult:
    """Check s3:PutObject permission by attempting a dry-run-style operation."""
    s3 = session.client("s3", region_name=region)
    test_key = f"{prefix}/.preflight-check"
    try:
        # Use head_object on a non-existent key to test bucket access,
        # then try a small put to verify write access
        s3.put_object(
            Bucket=bucket,
            Key=test_key,
            Body=b"preflight-check",
        )
        # Clean up the test object
        s3.delete_object(Bucket=bucket, Key=test_key)
        return CheckResult(
            service="S3",
            action="s3:PutObject",
            status="allowed",
            message=f"Can write to s3://{bucket}/{prefix}/",
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("AccessDenied", "403"):
            return CheckResult(
                service="S3",
                action="s3:PutObject",
                status="denied",
                message=f"Cannot write to s3://{bucket}/{prefix}/",
                requires_admin=False,
            )
        return CheckResult(
            service="S3",
            action="s3:PutObject",
            status="error",
            message=f"Unexpected error: {e}",
        )


def check_lambda_create(session: boto3.Session, region: str) -> CheckResult:
    """Check lambda:CreateFunction permission using IAM policy simulation."""
    iam = session.client("iam")
    caller_arn = session.client("sts").get_caller_identity()["Arn"]

    # Extract the role ARN from the assumed-role ARN
    # arn:aws:sts::ACCOUNT:assumed-role/ROLE_NAME/SESSION → arn:aws:iam::ACCOUNT:role/ROLE_NAME
    if ":assumed-role/" in caller_arn:
        parts = caller_arn.split(":")
        account = parts[4]
        role_name = parts[5].split("/")[1]
        role_arn = f"arn:aws:iam::{account}:role/{role_name}"
    else:
        role_arn = caller_arn

    try:
        response = iam.simulate_principal_policy(
            PolicySourceArn=role_arn,
            ActionNames=["lambda:CreateFunction"],
            ResourceArns=[f"arn:aws:lambda:{region}:*:function:*"],
        )
        decision = response["EvaluationResults"][0]["EvalDecision"]
        if decision == "allowed":
            return CheckResult(
                service="Lambda",
                action="lambda:CreateFunction",
                status="allowed",
                message="Can create Lambda functions.",
            )
        return CheckResult(
            service="Lambda",
            action="lambda:CreateFunction",
            status="denied",
            message="Cannot create Lambda functions. Use an elevated role for this step.",
            requires_admin=True,
        )
    except ClientError as e:
        # If we can't simulate, try to infer from the error
        code = e.response["Error"]["Code"]
        if code == "AccessDenied":
            # Can't even simulate — likely a scoped role
            return CheckResult(
                service="Lambda",
                action="lambda:CreateFunction",
                status="denied",
                message="Cannot simulate policies (likely a scoped role). "
                "Lambda creation may require an elevated role.",
                requires_admin=True,
            )
        return CheckResult(
            service="Lambda",
            action="lambda:CreateFunction",
            status="error",
            message=f"Could not verify: {e}",
        )


def check_lambda_invoke(
    session: boto3.Session, region: str, function_name: str | None = None
) -> CheckResult:
    """Check lambda:InvokeFunction permission."""
    iam = session.client("iam")
    caller_arn = session.client("sts").get_caller_identity()["Arn"]

    if ":assumed-role/" in caller_arn:
        parts = caller_arn.split(":")
        account = parts[4]
        role_name = parts[5].split("/")[1]
        role_arn = f"arn:aws:iam::{account}:role/{role_name}"
    else:
        role_arn = caller_arn

    resource_arn = f"arn:aws:lambda:{region}:*:function:*"
    if function_name:
        account = caller_arn.split(":")[4]
        resource_arn = f"arn:aws:lambda:{region}:{account}:function:{function_name}"

    try:
        response = iam.simulate_principal_policy(
            PolicySourceArn=role_arn,
            ActionNames=["lambda:InvokeFunction"],
            ResourceArns=[resource_arn],
        )
        decision = response["EvaluationResults"][0]["EvalDecision"]
        if decision == "allowed":
            return CheckResult(
                service="Lambda",
                action="lambda:InvokeFunction",
                status="allowed",
                message="Can invoke Lambda functions.",
            )
        return CheckResult(
            service="Lambda",
            action="lambda:InvokeFunction",
            status="denied",
            message="Cannot invoke Lambda functions. Bedrock validates this at job creation. "
            "Ensure a resource-based policy grants your role access, or use an elevated role.",
            requires_admin=True,
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "AccessDenied":
            return CheckResult(
                service="Lambda",
                action="lambda:InvokeFunction",
                status="denied",
                message="Cannot simulate policies. Lambda invoke permission is unclear.",
                requires_admin=True,
            )
        return CheckResult(
            service="Lambda",
            action="lambda:InvokeFunction",
            status="error",
            message=f"Could not verify: {e}",
        )


def check_iam_create_role(session: boto3.Session) -> CheckResult:
    """Check iam:CreateRole permission."""
    iam = session.client("iam")
    caller_arn = session.client("sts").get_caller_identity()["Arn"]

    if ":assumed-role/" in caller_arn:
        parts = caller_arn.split(":")
        account = parts[4]
        role_name = parts[5].split("/")[1]
        role_arn = f"arn:aws:iam::{account}:role/{role_name}"
    else:
        role_arn = caller_arn

    try:
        response = iam.simulate_principal_policy(
            PolicySourceArn=role_arn,
            ActionNames=["iam:CreateRole", "iam:AttachRolePolicy"],
            ResourceArns=["arn:aws:iam::*:role/*"],
        )
        denied = [
            r["EvalActionName"]
            for r in response["EvaluationResults"]
            if r["EvalDecision"] != "allowed"
        ]
        if not denied:
            return CheckResult(
                service="IAM",
                action="iam:CreateRole + iam:AttachRolePolicy",
                status="allowed",
                message="Can create IAM roles and attach policies.",
            )
        return CheckResult(
            service="IAM",
            action="iam:CreateRole + iam:AttachRolePolicy",
            status="denied",
            message=f"Denied: {', '.join(denied)}. Use an elevated role for IAM operations.",
            requires_admin=True,
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "AccessDenied":
            return CheckResult(
                service="IAM",
                action="iam:CreateRole + iam:AttachRolePolicy",
                status="denied",
                message="Cannot simulate policies. IAM operations likely require an elevated role.",
                requires_admin=True,
            )
        return CheckResult(
            service="IAM",
            action="iam:CreateRole + iam:AttachRolePolicy",
            status="error",
            message=f"Could not verify: {e}",
        )


def check_bedrock_create_job(session: boto3.Session, region: str) -> CheckResult:
    """Check bedrock:CreateAdvancedPromptOptimizationJob permission."""
    iam = session.client("iam")
    caller_arn = session.client("sts").get_caller_identity()["Arn"]

    if ":assumed-role/" in caller_arn:
        parts = caller_arn.split(":")
        account = parts[4]
        role_name = parts[5].split("/")[1]
        role_arn = f"arn:aws:iam::{account}:role/{role_name}"
    else:
        role_arn = caller_arn

    try:
        response = iam.simulate_principal_policy(
            PolicySourceArn=role_arn,
            ActionNames=[
                "bedrock:CreateAdvancedPromptOptimizationJob",
                "bedrock:GetFoundationModel",
            ],
            ResourceArns=["*"],
        )
        denied = [
            r["EvalActionName"]
            for r in response["EvaluationResults"]
            if r["EvalDecision"] != "allowed"
        ]
        if not denied:
            return CheckResult(
                service="Bedrock",
                action="bedrock:CreateAdvancedPromptOptimizationJob + GetFoundationModel",
                status="allowed",
                message="Can create Advanced Prompt Optimization jobs and query model info.",
            )
        return CheckResult(
            service="Bedrock",
            action="bedrock:CreateAdvancedPromptOptimizationJob + GetFoundationModel",
            status="denied",
            message=f"Denied: {', '.join(denied)}. Bedrock access may need to be granted.",
            requires_admin=False,
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "AccessDenied":
            return CheckResult(
                service="Bedrock",
                action="bedrock:CreateAdvancedPromptOptimizationJob + GetFoundationModel",
                status="denied",
                message="Cannot simulate policies. Bedrock permissions are unclear.",
                requires_admin=False,
            )
        return CheckResult(
            service="Bedrock",
            action="bedrock:CreateAdvancedPromptOptimizationJob + GetFoundationModel",
            status="error",
            message=f"Could not verify: {e}",
        )


def print_report(report: PreflightReport) -> None:
    """Print a formatted preflight report."""
    print("=" * 60)
    print("Advanced Prompt Optimization Workflow — Pre-flight Permissions Check")
    print("=" * 60)
    print()
    print(f"  Caller: {report.identity_arn}")
    print(f"  Account: {report.account_id}")
    print()
    print("-" * 60)

    for result in report.results:
        if result.status == "allowed":
            icon = "✓"
        elif result.status == "denied":
            icon = "✗"
        else:
            icon = "?"
        print(f"  {icon} [{result.service}] {result.action}")
        if result.message:
            print(f"    {result.message}")

    print("-" * 60)
    print()

    if report.all_passed:
        print("  All checks passed. You can run the full workflow with this role.")
    else:
        denied = report.denied_results
        print(f"  {len(denied)} permission(s) missing.")
        if report.admin_required:
            print()
            print("  The following operations require an elevated (admin) role:")
            for r in report.admin_required:
                print(f"    • {r.action}")
            print()
            print("  Recommendation: Use your default role for S3 uploads, job creation,")
            print("  and monitoring. Switch to an admin role (--profile) only for Lambda")
            print("  and IAM operations.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-flight permissions check for the Advanced Prompt Optimization workflow."
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="S3 bucket that will be used for the dataset and images.",
    )
    parser.add_argument(
        "--s3-prefix",
        default="prompt-optimization",
        help="S3 key prefix to test write access (default: prompt-optimization).",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1).",
    )
    parser.add_argument(
        "--profile",
        help="AWS profile to test (default: uses default credentials).",
    )
    parser.add_argument(
        "--lambda-function",
        help="Existing Lambda function name to check invoke permission against.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON.",
    )

    args = parser.parse_args()

    session_kwargs: dict = {}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs)

    report = PreflightReport()

    # Identity
    print("Checking caller identity...", file=sys.stderr)
    try:
        report.identity_arn, report.account_id = check_identity(session)
    except Exception as e:
        print(f"ERROR: Could not determine caller identity: {e}", file=sys.stderr)
        sys.exit(1)

    # S3
    print("Checking S3 write access...", file=sys.stderr)
    report.results.append(check_s3_put(session, args.bucket, args.s3_prefix, args.region))

    # Lambda
    print("Checking Lambda permissions...", file=sys.stderr)
    report.results.append(check_lambda_create(session, args.region))
    report.results.append(
        check_lambda_invoke(session, args.region, args.lambda_function)
    )

    # IAM
    print("Checking IAM permissions...", file=sys.stderr)
    report.results.append(check_iam_create_role(session))

    # Bedrock
    print("Checking Bedrock permissions...", file=sys.stderr)
    report.results.append(check_bedrock_create_job(session, args.region))

    print(file=sys.stderr)

    if args.json_output:
        output = {
            "identity_arn": report.identity_arn,
            "account_id": report.account_id,
            "all_passed": report.all_passed,
            "results": [
                {
                    "service": r.service,
                    "action": r.action,
                    "status": r.status,
                    "message": r.message,
                    "requires_admin": r.requires_admin,
                }
                for r in report.results
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        print_report(report)

    if not report.all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
