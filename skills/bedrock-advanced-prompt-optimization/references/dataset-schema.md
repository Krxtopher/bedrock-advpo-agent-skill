# Input Dataset Schema

Each line in the JSONL file must follow this schema:

```json
{
  "version": "bedrock-2026-05-14",
  "templateId": "string",
  "promptTemplate": "string with optional {{variableName}} placeholders",
  "steeringCriteria": ["string"],
  "customEvaluationMetricLabel": "string",
  "customLLMJConfig": {
    "customLLMJPrompt": "string using {{prompt}}, {{response}}, {{referenceResponse}}",
    "customLLMJModelId": "string"
  },
  "evaluationMetricLambdaArn": "string",
  "evaluationSamples": [
    {
      "inputVariables": [{"variableName": "value"}],
      "referenceResponse": "string",
      "inputVariablesMultimodal": [
        {"name": {"type": "IMAGE|PDF", "s3Uri": "s3://..."}}
      ]
    }
  ]
}
```

## Key Rules

- `inputVariables` must be a **list of single-key objects** (NOT a dict with multiple keys)
- For multimodal-only prompts, **omit `inputVariables` entirely** from each sample
- Multimodal files are sent alongside the prompt, NOT referenced via `{{placeholder}}` syntax
- `{{placeholder}}` variables represent the parts Advanced Prompt Optimization **preserves** — Advanced Prompt Optimization rewrites everything else in the template
- Choose ONE evaluation method per template (or omit all for system default)
- `referenceResponse` is optional but strongly recommended for best results
- Maximum 20 text variables per template
- Maximum 2 multimodal files per sample

## Common Mistakes

- Providing both `steeringCriteria` AND `customLLMJConfig`/`evaluationMetricLambdaArn` → ValidationException
- Missing `customEvaluationMetricLabel` when using LLMJ or Lambda → ValidationException
- Multiple keys in one `inputVariables` object → silent failure
- Using single curly brackets `{variable}` instead of double `{{variable}}`
- `inputVariables` keys not matching `{{variableName}}` placeholders in the template
- Using `description` instead of `jobDescription` in the API (the CLI script handles this)
- Using `encryptionConfig` instead of `encryptionKeyArn` in the API (the CLI script handles this)

## Output Layout

For a job with output S3 URI `s3://my-bucket/prompt-optimization/my-job/output/`, results land at:

    s3://my-bucket/prompt-optimization/my-job/output/<job-id>/advanced_prompt_optimization_results.jsonl

where `<job-id>` is the trailing segment of the job ARN. Each job gets its own subfolder, so you can reuse the same output prefix across many jobs safely. CI integrations can fetch results directly without going through `parse_results.py`.
