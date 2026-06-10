You are evaluating the quality of a model-generated summary.

The model was given content and asked to produce a summary.

## Model's Prompt:
{{prompt}}

## Model's Response:
{{response}}

## Reference Summary:
{{referenceResponse}}

## Evaluation Instructions:
Evaluate the model's summary on these dimensions:
1. **Completeness** (0-0.4): Does it capture all key points from the reference?
2. **Accuracy** (0-0.3): Is all stated information factually correct? No hallucinations?
3. **Conciseness** (0-0.2): Is it appropriately brief without unnecessary detail?
4. **Coherence** (0-0.1): Is it well-structured and readable?

Sum the scores across all dimensions for a total from 0.0 to 1.0.

Return a score from 0.0 to 1.0 representing overall summary quality.
