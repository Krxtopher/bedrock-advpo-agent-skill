"""Manage Bedrock Advanced Prompt Optimization jobs.

Supports: status, list, stop, delete operations.
"""

import argparse
import json
import sys

import boto3


def get_client(region: str, profile: str | None = None):
    """Create a Bedrock client."""
    session_kwargs: dict = {}
    if profile:
        session_kwargs["profile_name"] = profile
    session = boto3.Session(**session_kwargs)
    return session.client("bedrock", region_name=region)


def get_status(client, job_arn: str) -> dict:
    """Get the status of an optimization job."""
    return client.get_advanced_prompt_optimization_job(jobIdentifier=job_arn)


def list_jobs(client, max_results: int = 20) -> dict:
    """List optimization jobs."""
    return client.list_advanced_prompt_optimization_jobs(maxResults=max_results)


def stop_job(client, job_arn: str) -> None:
    """Stop a running optimization job."""
    client.stop_advanced_prompt_optimization_job(jobIdentifier=job_arn)


def delete_jobs(client, job_arns: list[str]) -> dict:
    """Batch delete optimization jobs."""
    return client.batch_delete_advanced_prompt_optimization_job(
        jobIdentifiers=job_arns
    )


def format_status_output(response: dict) -> str:
    """Format job status for display."""
    lines = [
        f"Job: {response.get('jobName', 'N/A')}",
        f"  ARN: {response.get('jobArn', 'N/A')}",
        f"  Status: {response.get('jobStatus', 'N/A')}",
    ]

    if response.get("description"):
        lines.append(f"  Description: {response['description']}")

    if response.get("creationTime"):
        lines.append(f"  Created: {response['creationTime']}")

    if response.get("lastModifiedTime"):
        lines.append(f"  Last Modified: {response['lastModifiedTime']}")

    if response.get("failureMessage"):
        lines.append(f"  Failure: {response['failureMessage']}")

    if response.get("modelConfigurations"):
        models = [m.get("modelId", "?") for m in response["modelConfigurations"]]
        lines.append(f"  Models: {models}")

    if response.get("inputConfig"):
        lines.append(f"  Input: {response['inputConfig'].get('s3Uri', 'N/A')}")

    if response.get("outputConfig"):
        lines.append(f"  Output: {response['outputConfig'].get('s3Uri', 'N/A')}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage Bedrock Advanced Prompt Optimization jobs."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute.")

    # Status command
    status_parser = subparsers.add_parser("status", help="Get job status.")
    status_parser.add_argument("--job-arn", required=True, help="Job ARN.")
    status_parser.add_argument("--region", default="us-east-1", help="AWS region.")
    status_parser.add_argument("--profile", help="AWS profile name.")
    status_parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output raw JSON."
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List jobs.")
    list_parser.add_argument(
        "--max-results", type=int, default=20, help="Max results (default: 20)."
    )
    list_parser.add_argument("--region", default="us-east-1", help="AWS region.")
    list_parser.add_argument("--profile", help="AWS profile name.")
    list_parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output raw JSON."
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop a running job.")
    stop_parser.add_argument("--job-arn", required=True, help="Job ARN.")
    stop_parser.add_argument("--region", default="us-east-1", help="AWS region.")
    stop_parser.add_argument("--profile", help="AWS profile name.")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete jobs.")
    delete_parser.add_argument(
        "--job-arns", nargs="+", required=True, help="Job ARN(s) to delete."
    )
    delete_parser.add_argument("--region", default="us-east-1", help="AWS region.")
    delete_parser.add_argument("--profile", help="AWS profile name.")
    delete_parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output raw JSON."
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        client = get_client(args.region, getattr(args, "profile", None))

        if args.command == "status":
            response = get_status(client, args.job_arn)
            if args.json_output:
                response.pop("ResponseMetadata", None)
                print(json.dumps(response, indent=2, default=str))
            else:
                print(format_status_output(response))

        elif args.command == "list":
            response = list_jobs(client, args.max_results)
            if args.json_output:
                response.pop("ResponseMetadata", None)
                print(json.dumps(response, indent=2, default=str))
            else:
                jobs = response.get("advancedPromptOptimizationJobSummaries", [])
                if not jobs:
                    print("No jobs found.")
                else:
                    print(f"Found {len(jobs)} job(s):\n")
                    for job in jobs:
                        status = job.get("jobStatus", "?")
                        name = job.get("jobName", "?")
                        arn = job.get("jobArn", "?")
                        created = job.get("creationTime", "?")
                        print(f"  [{status}] {name}")
                        print(f"    ARN: {arn}")
                        print(f"    Created: {created}")
                        print()

        elif args.command == "stop":
            stop_job(client, args.job_arn)
            print(f"Stop requested for: {args.job_arn}")

        elif args.command == "delete":
            response = delete_jobs(client, args.job_arns)
            if args.json_output:
                response.pop("ResponseMetadata", None)
                print(json.dumps(response, indent=2, default=str))
            else:
                for result in response.get("results", []):
                    status = result.get("status", "?")
                    job_id = result.get("jobIdentifier", "?")
                    print(f"  {job_id}: {status}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
