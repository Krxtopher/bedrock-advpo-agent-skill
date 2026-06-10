You are evaluating a model's classification accuracy.

The model was given input and asked to classify it into one or more categories.

## Model's Prompt:
{{prompt}}

## Model's Response:
{{response}}

## Expected Classification:
{{referenceResponse}}

## Evaluation Instructions:
1. Parse the model's response to identify the predicted classification(s).
2. Compare against the expected classification.
3. Scoring:
   - Exact match on primary classification: 1.0
   - Correct primary but wrong secondary labels: 0.75
   - Related/adjacent category (reasonable confusion): 0.25
   - Completely wrong classification: 0.0
   - No classification provided or unparseable response: 0.0

Return a score from 0.0 to 1.0 representing classification accuracy.
