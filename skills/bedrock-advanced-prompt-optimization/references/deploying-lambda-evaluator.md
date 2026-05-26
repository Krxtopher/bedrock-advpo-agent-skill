# Deploying a Lambda Evaluator

When using a custom Lambda evaluator, you need to deploy a Lambda function and configure permissions. Here's the process:

## Lambda Function Requirements

- Single `.py` file with all code
- Handler: `lambda_function.lambda_handler`
- Must implement `compute_score(preds, golds)` returning `{"score": float, "scores": [float, ...]}`
- Scores should be continuous (0.0 to 1.0) for best optimization convergence
- Never crash — return 0.0 on errors
- Timeout: set to 900 seconds (max) for large batches

## AdvPO Event Format

The AdvPO service invokes your Lambda with this exact event structure:

```json
{"preds": ["model_output_1", "model_output_2", ...], "golds": ["reference_1", "reference_2", ...]}
```

- `preds` — the model's raw text outputs (one per evaluation sample)
- `golds` — the `referenceResponse` values from your dataset (one per sample)

**Important:** The keys are `preds` and `golds` — not `predictions`/`groundTruths` or any other variation. Your `lambda_handler` must use exactly these keys:

```python
def lambda_handler(event, context):
    preds = event.get("preds", [])
    golds = event.get("golds", [])
    return compute_score(preds, golds)
```

## Deployment Steps

1. **Create an IAM role** with trust policy for both `lambda.amazonaws.com` and `bedrock.amazonaws.com`:
   ```bash
   aws iam create-role --role-name my-evaluator-role \
     --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":["lambda.amazonaws.com","bedrock.amazonaws.com"]},"Action":"sts:AssumeRole"}]}'
   aws iam attach-role-policy --role-name my-evaluator-role \
     --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
   ```

2. **Zip and deploy the function:**
   ```bash
   zip -j evaluator.zip lambda_function.py
   aws lambda create-function --function-name my-evaluator \
     --runtime python3.12 --handler lambda_function.lambda_handler \
     --role arn:aws:iam::ACCOUNT:role/my-evaluator-role \
     --zip-file fileb://evaluator.zip --timeout 900
   ```

3. **Add resource-based permissions** (both Bedrock service AND your caller role):
   ```bash
   aws lambda add-permission --function-name my-evaluator \
     --statement-id AllowBedrockInvoke --action lambda:InvokeFunction \
     --principal bedrock.amazonaws.com
   aws lambda add-permission --function-name my-evaluator \
     --statement-id AllowCallerInvoke --action lambda:InvokeFunction \
     --principal arn:aws:iam::ACCOUNT:role/YOUR-CALLER-ROLE
   ```

   Both permissions are required — Bedrock validates that the caller can invoke the Lambda before accepting the job.

4. **Tag the resources** for ownership tracking:
   ```bash
   aws lambda tag-resource --resource arn:aws:lambda:REGION:ACCOUNT:function:my-evaluator \
     --tags owner=YOUR-ALIAS
   aws iam tag-role --role-name my-evaluator-role --tags Key=owner,Value=YOUR-ALIAS
   ```

## Important: Test Before Deploying

Before zipping and deploying the Lambda function, you must write and run a local test script (`test_evaluator.py`) that validates the `compute_score` function. See `references/testing-lambda-evaluator.md` for requirements and an example template. A broken evaluator silently corrupts the optimization — always confirm it scores correctly on real sample data first.

