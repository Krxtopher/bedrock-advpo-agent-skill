You are evaluating a model's ability to extract structured data from a document.

The model was given a document and asked to extract specific fields into a JSON object.

## Model's Prompt:
{{prompt}}

## Model's Response:
{{response}}

## Expected Ground Truth:
{{referenceResponse}}

## Evaluation Instructions:
Compare the model's response against the ground truth field by field:
1. Parse both as JSON. If the model's response is not valid JSON, score 0.
2. For each field in the ground truth:
   - Exact match (case-insensitive, whitespace-trimmed): full credit
   - Partial match (correct value but wrong format, e.g. date format differs): half credit
   - Missing, null when expected, or incorrect value: no credit
3. Calculate the percentage of fields correctly extracted.

Return a score from 0.0 to 1.0 representing extraction accuracy.
