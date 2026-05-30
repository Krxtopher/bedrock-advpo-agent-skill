# Test Plan

Unit tests (pytest) for the Bedrock Advanced Prompt Optimization skill scripts.

---

## Lambda Evaluator Template (`examples/lambda-evaluator-template.py`)

### Scoring Logic

- **Exact match scoring:** Given matching pred/gold JSON, `_score_single` returns 1.0
- **Partial match scoring:** Given 3/5 fields matching, `_score_single` returns 0.6
- **No match scoring:** Given completely different pred/gold, `_score_single` returns 0.0
- **Empty gold object:** Returns 0.0 (not a division-by-zero error)
- **Malformed pred JSON:** Returns 0.0 (not an exception)
- **None pred input:** Returns 0.0 (not an exception)
- **Exception guard:** If scoring logic raises any exception, `_score_single` returns 0.0 and prints a diagnostic

### Batch Scoring

- **compute_score averages correctly:** Given scores [1.0, 0.5, 0.0], returns `{"score": 0.5, "scores": [1.0, 0.5, 0.0]}`
- **Empty batch:** Returns `{"score": 0.0, "scores": []}`

### Code Fence Handling

- **strip_code_fences removes ```json wrapper:** Input with fences returns clean JSON
- **strip_code_fences passes through clean text:** Input without fences is unchanged
- **Tolerant mode:** `parse_json_output` strips fences and parses successfully
- **Strict mode:** `parse_json_output` raises ValueError when fences are present and `TOLERANT_CODE_FENCES = False`

### Lambda Handler

- **Correct event keys:** Handler reads `preds` and `golds` from event dict
- **Missing keys:** Handler defaults to empty lists when keys are absent
- **Return format:** Handler returns dict with `score` (float) and `scores` (list of floats)

---

## Dataset Preparation (`scripts/prepare_dataset.py`)

### Placeholder Extraction

- **Single placeholder:** `"Hello {{name}}"` → `{"name"}`
- **Multiple placeholders:** `"{{a}} and {{b}}"` → `{"a", "b"}`
- **No placeholders:** `"Hello world"` → empty set
- **Duplicate placeholders:** `"{{x}} {{x}}"` → `{"x"}` (deduplicated)

### Sample Validation

- **Valid text-only sample:** No errors when inputVariables match template placeholders
- **Missing variable:** Error reported when a placeholder has no corresponding inputVariable
- **Extra variable:** Error reported when inputVariable doesn't match any placeholder
- **Multimodal sample without text:** Valid when inputVariablesMultimodal is present and template has no placeholders
- **Too many multimodal files:** Error when sample has >2 multimodal entries
- **Invalid multimodal type:** Error when type is not IMAGE or PDF
- **Missing s3Uri:** Error when multimodal entry lacks s3Uri
- **Over 100 samples:** Error reported

### Evaluation Method Exclusivity

- **Multiple methods specified:** Script exits with error when both `--steering-criteria` and `--lambda-arn` are provided
- **LLMJ without model:** Script exits with error when `--llmj-prompt` is given without `--llmj-model`
- **Missing metric label:** Script exits with error when `--lambda-arn` is given without `--metric-label`
- **Over 5 steering criteria:** Script exits with error

### Output Format

- **JSONL structure:** Output contains valid JSON on each line
- **Schema version:** Record includes `"version": "bedrock-2026-05-14"`
- **inputVariables format:** Variables are formatted as list of single-key objects
- **Append mode:** `--append` adds to existing file without overwriting

---

## Job Creation (`scripts/create_job.py`)

### Job Name Suffix

- **Suffix is appended:** Output job name is `{input}-{4-char-hex}`
- **Suffix is unique:** Two calls produce different suffixes

### Model Access Check

- **Accessible model:** Returns empty list (no issues)
- **Inaccessible model (ResourceNotFoundException):** Returns model ID in list
- **LEGACY status model:** Prints warning but does not block
- **Throttling error:** Prints warning but does not block

### CRIS Inference Profile Check

- **Non-prefixed model ID:** `check_inference_profile` returns True (no check needed)
- **Prefixed ID with long first segment:** Returns True (not a region prefix)
- **Prefixed ID found in profiles list:** Returns True
- **Prefixed ID not found in profiles list:** Returns False
- **ClientError during listing:** Returns True (fail-open)

### Multimodal Compatibility Check

- **Dataset has no multimodal:** `check_multimodal_compatible` returns True regardless of model
- **Model supports IMAGE input:** Returns True when dataset has multimodal
- **Model is text-only:** Returns (False, error message) when dataset has multimodal
- **ClientError during model lookup:** Returns True (fail-open)

### Tag Parsing

- **Valid tags:** `["owner=schultkr", "env=dev"]` → `[{"key": "owner", "value": "schultkr"}, ...]`
- **Invalid tag format:** Script exits with error for tag without `=`

### Argument Validation

- **Over 5 models:** Script exits with error
- **--skip-preflight:** Bypasses all preflight checks

---

## Results Parsing (`scripts/parse_results.py`)

### S3 Key Derivation

- **Standard URI:** `get_results_key("arn:.../abc123", "s3://bucket/output/")` → `("bucket", "output/abc123/advanced_prompt_optimization_results.jsonl")`
- **URI without trailing slash:** Still produces correct key
- **URI with no prefix:** `s3://bucket` → key is `abc123/advanced_prompt_optimization_results.jsonl`

### Score Formatting

- **Score improvement displayed:** Shows original avg, optimized avg, and delta
- **Positive improvement:** Shows `+` prefix
- **Negative improvement:** Shows `-` prefix (regression)

---

## Prompt Extraction (`scripts/extract_prompt.py`)

### Brace Unescaping

- **Double braces converted:** `"{{name}}"` in result becomes `"{name}"` in output
- **Mixed content:** Only `{{`/`}}` pairs are unescaped, other text preserved

### Template/Model Selection

- **Single template, single model:** Extracts without requiring `--template-id` or `--model`
- **Multiple templates without --template-id:** Uses first, prints warning
- **Multiple models without --model:** Uses first, prints warning
- **Non-existent template-id:** Exits with error listing available IDs
- **Non-existent model:** Exits with error listing available models
- **Non-SUCCESS status:** Prints warning but still extracts

---

## Multimodal Samples Builder (`scripts/build_multimodal_samples.py`)

### File Discovery

- **With ground truth:** Pairs `*-ground_truth.json` files with matching document files
- **Without ground truth:** Discovers all files matching `--doc-ext`
- **Missing document for ground truth:** Skips with warning
- **No ground truth files found:** Exits with error (suggests `--no-ground-truth`)
- **Custom gt-suffix:** Respects `--gt-suffix` for pairing

### Output Format

- **Sample structure (with GT):** Contains `inputVariablesMultimodal` and `referenceResponse`
- **Sample structure (no GT):** Contains `inputVariablesMultimodal` only, no `referenceResponse`
- **Shared input variables:** When `--input-variables` is provided, each sample includes them
- **S3 URI construction:** Uses `s3://{bucket}/{s3-prefix}/{filename}`
