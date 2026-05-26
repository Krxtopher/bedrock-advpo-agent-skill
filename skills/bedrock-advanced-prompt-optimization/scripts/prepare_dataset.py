"""Prepare a JSONL input dataset for Bedrock Advanced Prompt Optimization.

This script validates inputs and produces a correctly formatted JSONL file
that can be uploaded to S3 and used with CreateAdvancedPromptOptimizationJob.
"""

import argparse
import json
import re
import sys
from pathlib import Path


SCHEMA_VERSION = "bedrock-2026-05-14"

VALID_JUDGE_MODELS = [
    "anthropic.claude-opus-4-6-v1",
    "anthropic.claude-sonnet-4-5-20250929-v1:0",
    "anthropic.claude-sonnet-4-6",
]

VALID_MULTIMODAL_TYPES = ["IMAGE", "PDF"]


def extract_placeholders(template: str) -> set[str]:
    """Extract {{variableName}} placeholders from a prompt template."""
    return set(re.findall(r"\{\{(\w+)\}\}", template))


def validate_samples(
    samples: list[dict],
    expected_variables: set[str],
) -> list[str]:
    """Validate evaluation samples against the prompt template variables."""
    errors: list[str] = []

    if not samples:
        errors.append("At least one evaluation sample is required.")
        return errors

    if len(samples) > 100:
        errors.append(f"Maximum 100 evaluation samples allowed, got {len(samples)}.")

    for i, sample in enumerate(samples):
        has_text = "inputVariables" in sample and sample["inputVariables"]
        has_multimodal = (
            "inputVariablesMultimodal" in sample and sample["inputVariablesMultimodal"]
        )

        if not has_text and not has_multimodal:
            errors.append(
                f"Sample {i}: must have at least one of 'inputVariables' or "
                "'inputVariablesMultimodal'."
            )
            continue

        if has_text:
            input_vars = sample["inputVariables"]
            if isinstance(input_vars, list):
                provided_vars = set()
                for item in input_vars:
                    if isinstance(item, dict):
                        provided_vars.update(item.keys())
            else:
                provided_vars = set(input_vars.keys())
            missing = expected_variables - provided_vars
            extra = provided_vars - expected_variables
            if missing:
                errors.append(
                    f"Sample {i}: missing variables {missing} "
                    f"(expected from template: {expected_variables})."
                )
            if extra:
                errors.append(
                    f"Sample {i}: extra variables {extra} not in template placeholders."
                )

        if has_multimodal:
            multimodal_items = sample["inputVariablesMultimodal"]
            if len(multimodal_items) > 2:
                errors.append(
                    f"Sample {i}: maximum 2 multimodal files per sample, "
                    f"got {len(multimodal_items)}."
                )
            for j, item in enumerate(multimodal_items):
                if not isinstance(item, dict) or len(item) != 1:
                    errors.append(
                        f"Sample {i}, multimodal {j}: must be a single-key object."
                    )
                    continue
                name = list(item.keys())[0]
                entry = item[name]
                if "type" not in entry:
                    errors.append(
                        f"Sample {i}, multimodal '{name}': missing 'type' field."
                    )
                elif entry["type"] not in VALID_MULTIMODAL_TYPES:
                    errors.append(
                        f"Sample {i}, multimodal '{name}': type must be one of "
                        f"{VALID_MULTIMODAL_TYPES}, got '{entry['type']}'."
                    )
                if "s3Uri" not in entry:
                    errors.append(
                        f"Sample {i}, multimodal '{name}': missing 's3Uri' field."
                    )

    return errors


def format_input_variables(variables: dict | list) -> list[dict]:
    """Convert variables to the required list-of-single-key-objects format."""
    if isinstance(variables, list):
        return variables
    return [{k: v} for k, v in variables.items()]


def build_dataset_record(
    template_id: str,
    prompt_template: str,
    samples: list[dict],
    steering_criteria: list[str] | None = None,
    llmj_prompt: str | None = None,
    llmj_model: str | None = None,
    metric_label: str | None = None,
    lambda_arn: str | None = None,
) -> dict:
    """Build a single JSONL record for the AdvPO input dataset."""
    record: dict = {
        "version": SCHEMA_VERSION,
        "templateId": template_id,
        "promptTemplate": prompt_template,
    }

    # Evaluation method (pick one)
    if steering_criteria:
        record["steeringCriteria"] = steering_criteria
    elif llmj_prompt and llmj_model:
        record["customEvaluationMetricLabel"] = metric_label or "custom_metric"
        record["customLLMJConfig"] = {
            "customLLMJPrompt": llmj_prompt,
            "customLLMJModelId": llmj_model,
        }
    elif lambda_arn:
        record["customEvaluationMetricLabel"] = metric_label or "custom_metric"
        record["evaluationMetricLambdaArn"] = lambda_arn

    # Format evaluation samples
    evaluation_samples = []
    for sample in samples:
        formatted_sample: dict = {}

        if "inputVariables" in sample and sample["inputVariables"]:
            formatted_sample["inputVariables"] = format_input_variables(
                sample["inputVariables"]
            )
        # For multimodal-only samples, omit inputVariables entirely

        if "referenceResponse" in sample and sample["referenceResponse"]:
            formatted_sample["referenceResponse"] = sample["referenceResponse"]

        if "inputVariablesMultimodal" in sample and sample["inputVariablesMultimodal"]:
            formatted_sample["inputVariablesMultimodal"] = sample[
                "inputVariablesMultimodal"
            ]

        evaluation_samples.append(formatted_sample)

    record["evaluationSamples"] = evaluation_samples
    return record


def load_text_from_file_or_string(value: str | None, file_path: Path | None) -> str | None:
    """Load text content from either a direct string or a file path."""
    if file_path:
        if not file_path.exists():
            print(f"ERROR: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        return file_path.read_text().strip()
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a JSONL input dataset for Bedrock AdvPO."
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSONL file path.",
    )
    parser.add_argument(
        "--template-id",
        required=True,
        help="Unique identifier for this prompt template.",
    )

    # Prompt template: inline or file
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument(
        "--prompt-template",
        help="The prompt template with {{variableName}} placeholders (inline string).",
    )
    prompt_group.add_argument(
        "--prompt-template-file",
        type=Path,
        help="Path to a file containing the prompt template.",
    )

    parser.add_argument(
        "--samples",
        type=Path,
        required=True,
        help="Path to JSON file containing evaluation samples array.",
    )
    parser.add_argument(
        "--steering-criteria",
        nargs="+",
        help="Steering criteria strings (up to 5).",
    )

    # LLMJ prompt: inline or file
    llmj_group = parser.add_mutually_exclusive_group()
    llmj_group.add_argument(
        "--llmj-prompt",
        help="Custom LLM-as-a-judge prompt (inline). Use {{prompt}}, {{response}}, "
        "{{referenceResponse}} as placeholders.",
    )
    llmj_group.add_argument(
        "--llmj-prompt-file",
        type=Path,
        help="Path to a file containing the LLM-as-a-judge prompt.",
    )

    parser.add_argument(
        "--llmj-model",
        choices=VALID_JUDGE_MODELS,
        help="Judge model ID for custom LLM-as-a-judge.",
    )
    parser.add_argument(
        "--lambda-arn",
        help="ARN of Lambda function for custom evaluation.",
    )
    parser.add_argument(
        "--metric-label",
        help="Label for custom evaluation metric (required with --llmj-prompt or "
        "--lambda-arn).",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing output file instead of overwriting.",
    )

    args = parser.parse_args()

    # Resolve prompt template from file or inline
    prompt_template = load_text_from_file_or_string(
        args.prompt_template, args.prompt_template_file
    )
    if not prompt_template:
        print("ERROR: Prompt template is empty.", file=sys.stderr)
        sys.exit(1)

    # Resolve LLMJ prompt from file or inline
    llmj_prompt = load_text_from_file_or_string(
        args.llmj_prompt, args.llmj_prompt_file
    )

    # Validate evaluation method exclusivity
    eval_methods = sum([
        bool(args.steering_criteria),
        bool(llmj_prompt),
        bool(args.lambda_arn),
    ])
    if eval_methods > 1:
        print(
            "ERROR: Choose only ONE evaluation method: --steering-criteria, "
            "--llmj-prompt/--llmj-prompt-file, or --lambda-arn.",
            file=sys.stderr,
        )
        sys.exit(1)

    if llmj_prompt and not args.llmj_model:
        print(
            "ERROR: --llmj-model is required when using --llmj-prompt or "
            "--llmj-prompt-file.",
            file=sys.stderr,
        )
        sys.exit(1)

    if (llmj_prompt or args.lambda_arn) and not args.metric_label:
        print(
            "ERROR: --metric-label is required when using --llmj-prompt/--llmj-prompt-file "
            "or --lambda-arn.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.steering_criteria and len(args.steering_criteria) > 5:
        print(
            "ERROR: Maximum 5 steering criteria allowed.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load samples
    samples_path = args.samples
    if not samples_path.exists():
        print(f"ERROR: Samples file not found: {samples_path}", file=sys.stderr)
        sys.exit(1)

    with open(samples_path) as f:
        samples = json.load(f)

    if not isinstance(samples, list):
        print("ERROR: Samples file must contain a JSON array.", file=sys.stderr)
        sys.exit(1)

    # Extract and validate placeholders
    placeholders = extract_placeholders(prompt_template)
    if placeholders and len(placeholders) > 20:
        print(
            f"ERROR: Maximum 20 text variables per template, found {len(placeholders)}.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate samples
    errors = validate_samples(samples, placeholders)
    if errors:
        print("Validation errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)

    # Build the record
    record = build_dataset_record(
        template_id=args.template_id,
        prompt_template=prompt_template,
        samples=samples,
        steering_criteria=args.steering_criteria,
        llmj_prompt=llmj_prompt,
        llmj_model=args.llmj_model,
        metric_label=args.metric_label,
        lambda_arn=args.lambda_arn,
    )

    # Write output
    mode = "a" if args.append else "w"
    with open(args.output, mode) as f:
        f.write(json.dumps(record) + "\n")

    action = "Appended to" if args.append else "Created"
    print(f"{action} {args.output}")
    print(f"  Template ID: {args.template_id}")
    print(f"  Placeholders: {placeholders or '(none — multimodal only)'}")
    print(f"  Samples: {len(samples)}")

    eval_method = "system default"
    if args.steering_criteria:
        eval_method = f"steering criteria: {args.steering_criteria}"
    elif llmj_prompt:
        eval_method = f"LLM-as-a-judge ({args.llmj_model})"
    elif args.lambda_arn:
        eval_method = f"Lambda: {args.lambda_arn}"
    print(f"  Evaluation: {eval_method}")


if __name__ == "__main__":
    main()
