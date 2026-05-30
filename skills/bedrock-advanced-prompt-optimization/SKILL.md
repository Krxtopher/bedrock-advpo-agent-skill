---
name: bedrock-advanced-prompt-optimization
description: >
  Create, manage, and analyze Bedrock Advanced Prompt Optimization jobs.
  Use when the user wants to optimize prompts, compare model performance, migrate
  between models, or prepare evaluation datasets for prompt optimization. Activate
  whenever you see mentions of prompt optimization, prompt tuning, model
  migration, evaluation-driven prompt improvement, prompt engineering at scale,
  A/B testing prompts across models, or improving prompt quality with ground truth
  data. Also use when the user mentions JSONL datasets for prompt evaluation,
  steering criteria, LLM-as-a-judge evaluation, or wants to benchmark a prompt
  across multiple foundation models. If the user says anything about making their
  prompts better or comparing how different models respond to the same prompt,
  this is the skill to use.
compatibility: Any coding agent that supports the Agent Skills standard (agentskills.io). Requires Python 3.10+, boto3, and AWS CLI.
metadata:
  author: schultkr
  version: "1.0"
---

> **IMPORTANT:** This skill is designed to work in vibe (conversational) sessions. Do NOT suggest switching to a spec session. Execute the workflow directly in the current session.

# Bedrock Advanced Prompt Optimization

**Naming convention:** When responding to users, always use the full formal name "Amazon Bedrock Advanced Prompt Optimization" on first mention in a conversation. After that initial introduction, you may use "Advanced Prompt Optimization" as shorthand.

This skill lets you work with Amazon Bedrock's Advanced Prompt Optimization feature. It provides CLI scripts to prepare input datasets, create and monitor optimization jobs, and parse results.

## What is Advanced Prompt Optimization?

Advanced Prompt Optimization takes your prompt templates, evaluation samples, and an evaluation method, then runs iterative inference → evaluate → rewrite loops. It outputs optimized prompts with evaluation metrics for each target model.

**How it optimizes:** The optimizer rewrites the *static instruction text* in your prompt template to improve performance on the target model. Any `{{placeholder}}` variables are the parts it **preserves** — they represent the dynamic runtime inputs (user questions, context, etc.) that stay the same. Everything else in the template is fair game for rewriting.

## When Invoked Without a Request

If the user activates this skill without providing a specific task or question — for example, they just type the skill name — respond with a brief, friendly introduction:

1. Mention you've activated the Amazon Bedrock Advanced Prompt Optimization skill.
2. In 2–3 sentences, explain what Advanced Prompt Optimization does and the kind of value it provides
3. Mention the types of tasks you can help with (optimizing a prompt for a specific model, comparing prompt performance across models, preparing evaluation datasets, implementing and deploying custom evaluators)
4. Ask what they'd like to work on

Keep the introduction concise — no more than a short paragraph plus the question. Don't dump the full workflow or a wall of features. The goal is to orient the user and invite them to engage.

## Asking the User Questions

**Single-threaded information gathering:** Ask exactly ONE question at a time. Wait for the user's response before asking the next question. Never combine multiple questions into a single message — even if you know you'll need several pieces of information, ask them sequentially. This makes it easy for the user to give clear, focused answers.

**Educate as you go:** Assume the user has never used Advanced Prompt Optimization before. With each question, include a brief sentence or two explaining *why* you're asking and how their answer will influence the optimization process. When introducing a concept for the first time (e.g., "Lambda evaluator," "steering criteria," "ANLS*," "cross-region inference"), give a plain-language explanation of what it is before asking the user to make a decision about it. The user shouldn't have to Google a term to answer your question. Keep it concise — a sentence or two of context, not a paragraph of lecture.

When gathering information from the user, use multiple-choice questions **only** when the question has a finite, known set of valid options (e.g., single vs. multi-model, evaluation method, region). Use free-form text input for user-specific values (model name, S3 bucket, S3 prefix, job name, file paths, template IDs, Lambda ARNs). Never fabricate example values as multiple-choice options for user-specific inputs.

**Mandatory confirmations — never infer these from context:**
- **S3 bucket:** Always ask the user which S3 bucket to use. If the user's steering files or project context mention a bucket, offer it as a suggested default — but still confirm explicitly, since they may want to use a different one for this workflow.
- **AWS region:** Always ask the user which region to use. If context suggests a likely region (e.g., the bucket name contains a region, or a steering file specifies one), offer it as a suggested default — but still confirm explicitly. The Advanced Prompt Optimization job, S3 bucket, and Lambda must all be in the same region, so this choice matters.
- **S3 prefix:** Suggest a sensible default (e.g., `advpo/`) but confirm with the user before using it. They may have an existing folder structure or naming convention.

**Critical formatting rule:** When asking a free-form question, output ONLY the question as a single sentence or short paragraph. Do NOT follow it with numbered options, bullet-point suggestions, or any structured list — even "helpful" ones. Structured lists trigger interactive selection UIs that prevent the user from typing a free-form answer. If you want to offer a suggestion, put it inline in the question itself (e.g., "What S3 bucket should I use? If you used one previously, I can reuse that.") — never as a separate numbered item.

## Resource Tagging

Before creating any AWS resources (Lambda functions, IAM roles, optimization jobs, etc.), ask the user if they'd like to apply a tag. Ask once early in the workflow and reuse their answer for all resources created during the session. If they provide a tag, apply it consistently to every resource you create. If they decline, proceed without tags.

## File Organization

All files generated during the optimization workflow — samples, datasets, Lambda code, test scripts, results, and the resource tracking file — should be placed under a `prompt-optimization/` directory in the user's working directory. Create this directory at the start of the workflow if it doesn't exist. This keeps optimization artifacts organized and separate from the rest of the project.

```
prompt-optimization/
├── samples.json
├── dataset.jsonl
├── results.jsonl
├── advpo-resources.json
└── evaluator/
    ├── lambda_function.py
    └── test_evaluator.py
```

## Resource Tracking

Whenever you create an AWS resource (Lambda function, IAM role, S3 object, optimization job, etc.), append a reference to `prompt-optimization/advpo-resources.json`. Create the file if it doesn't exist. Format: `{"lambda": [{"id": "arn:...", "created": "2026-05-19"}], "iam_role": [...], "advpo_job": [...], "s3": [...]}`. Append to existing arrays — don't overwrite from a previous run.

## Resource Cleanup

After the optimization job completes and results have been successfully downloaded locally, offer to clean up the AWS resources that were created during the workflow. Use the cleanup script:

```bash
python .kiro/skills/bedrock-advpo/scripts/cleanup_resources.py \
  --resources prompt-optimization/advpo-resources.json \
  --region us-east-1
```

The script reads `advpo-resources.json`, groups resources by type, confirms deletion with the user for each type, and removes the entries from the file as they're deleted. Pass `--yes` to skip confirmation prompts, or `--types lambda s3` to delete only specific resource types.

Note: Some resources (like a Lambda evaluator) may be worth keeping for future optimization runs. Mention this to the user before running cleanup.

## Pre-requisite: AWS MCP Server Check

Before starting the workflow, check whether the AWS MCP server is configured and enabled. This skill works without it, but runs much more smoothly and consistently when it's available — the AWS MCP server provides direct access to AWS API calls, documentation lookups, and script execution that streamline many steps in the optimization workflow.

**How to check:**
1. Look for an MCP configuration file at `.kiro/settings/mcp.json` in the workspace, or at `~/.kiro/settings/mcp.json` at the user level.
2. Check if an entry named `aws-mcp` (or similar, e.g., `aws`, `aws-docs`) exists in the `mcpServers` object.
3. Verify that the entry's `"disabled"` field is either absent or set to `false`.

**If the AWS MCP server is NOT configured or is disabled:**
Inform the user that this skill works best with the AWS MCP server enabled, and suggest they set it up. Point them to the official setup documentation:

> The AWS MCP server isn't required for this skill, but it makes the workflow significantly smoother — especially for steps that interact with AWS services (S3 uploads, Lambda deployment, job monitoring). I'd recommend setting it up if you haven't already.
>
> Setup guide: https://docs.aws.amazon.com/agent-toolkit/latest/userguide/getting-started-aws-mcp-server.html

Then continue with the workflow regardless — the skill's Python scripts handle all AWS operations via boto3 and the AWS CLI, so nothing is blocked.

**If the AWS MCP server IS configured and enabled:**
Proceed without comment. No need to mention it to the user.

## Agent Workflow

When a user wants to optimize a prompt, follow this workflow in order. Each step has a corresponding CLI script that can be called directly.

**Before asking questions, inspect the workspace.** At the start of the workflow, look at the files in the user's project to understand what you're working with. Check for:
- Prompt files (`.md`, `.txt`) — these may be the prompt template to optimize
- Ground truth files (`*ground_truth*.json`, `*gt*.json`) — indicates structured evaluation data exists
- Image or PDF assets — suggests a multimodal extraction task
- An existing `prompt-optimization/` directory — indicates a previous run; check for `advpo-resources.json`, `samples.json`, or `dataset.jsonl` that can be reused
- Data schemas or example outputs — helps you understand the expected structure

Use what you find to ask more informed questions and offer specific recommendations. For example, if you see ground truth JSON files paired with images, you already know this is a structured extraction task with multimodal input — you can skip asking about the task type and instead confirm your understanding with the user.

If the user invokes this skill without providing details about their task (e.g., "use the Advanced Prompt Optimization skill" or "help me optimize a prompt"), briefly introduce what the service does, inspect the workspace for context, and then start at Step 1 with an informed question. Don't wait for the user to volunteer context — lead with what you've observed.

**Example interaction flow:**

### Pre-flight: Validate Permissions

Before starting the workflow, run the pre-flight permissions check to verify the caller has the access needed for each step. This prevents mid-workflow failures and helps the user decide which role to use.

```bash
python .kiro/skills/bedrock-advpo/scripts/preflight_check.py \
  --bucket my-bucket \
  --s3-prefix advpo \
  --region us-east-1 \
  --profile admin-933  # optional: test a specific profile
```

The script checks: S3 write access, Lambda create/invoke, IAM role creation, and Bedrock job creation. It reports which permissions are missing and which operations require an elevated role.

**Best practice — least privilege:** Use the default (scoped-down) role for most operations. Only pass `--profile <admin-profile>` for steps that require elevation (typically Lambda and IAM creation).

**Example interaction flow:**
```
User: "I want to optimize a prompt"
Agent: → Brief intro to Advanced Prompt Optimization, then Step 1: "Are you optimizing for a single model, or comparing across multiple?"
User: "Single model"
Agent: → Step 2: "Which model would you like to optimize for?"
User: "Nova 2 Lite"
Agent: → Confirms model, moves to Step 3.
```

### Step 1: Clarify the User's Goal

The first question determines the entire job configuration — getting it wrong means wasted time and money on an optimization that doesn't match the user's intent. Ask:

> Are you optimizing a prompt for a **single target model**, or are you **comparing/migrating across multiple models**?

This determines:
- **Single model optimization:** Pass one model to `--models`. The goal is to get the best possible prompt for that specific model.
- **Model comparison/migration:** Pass 2–5 models to `--models`. The goal is to see how the same prompt performs across models, or to find the best model for a given task.

**Important:** When you pass multiple models, the optimizer produces an independently-optimized prompt for each model — not a single shared prompt. This is great for migration ("which model performs best with its own optimized prompt?") but it's not a head-to-head model benchmark. If you want to compare model A and model B on the *same* prompt, run the original prompt through Bedrock InvokeModel directly with each model and compare scores.

Do NOT assume multi-model comparison. Default to single-model optimization unless the user explicitly asks to compare.

### Step 2: Select Target Model(s)

Advanced Prompt Optimization works with any text-generation model available through Amazon Bedrock. When helping the user choose:

1. **Ask as a free-form question.** Do NOT present model selection as a multiple-choice list or numbered options. Never output a list of models for the user to pick from — this triggers interactive selection UIs that bypass the grounding check. Instead, simply ask: "Which model would you like to optimize for?" with no options listed.

2. **Do NOT offer model recommendations.** Bedrock offers models from many providers, and the factors that go into choosing a model are complex and nuanced. Do not proactively suggest models or offer guidance on which to pick. If the user explicitly asks for help choosing, you may search the latest AWS documentation to provide basic details about model capabilities, but always inform them that the best way to choose a model is through running evaluations to compare performance — which is exactly what the multi-model comparison mode is designed for.

3. **Use human-friendly names in conversation.** When presenting model options to the user, use the model's display name (e.g., "Nova 2 Lite", "Claude Sonnet 4.5", "Llama 4 Maverick"). Only show the raw model ID (e.g., `amazon.nova-2-lite-v1:0`) when you're constructing the actual CLI command or if the user asks for it. People think in names, not version-stamped identifiers.

4. **Ground every suggestion in the model table below.** Only suggest models that appear in this table or that you have confirmed exist via the dynamic lookup command. Do not invent model names or IDs.

5. **Offer dynamic lookup when needed.** If the user asks about a model not in this table, or wants to see everything available in their account, run:
   ```bash
   aws bedrock list-foundation-models --region <region> \
     --query "modelSummaries[?contains(outputModalities, 'TEXT')].{id:modelId, name:modelName, provider:providerName}" \
     --output table
   ```

6. **Cross-region inference prefixes.** Many newer models require a prefix (`us.`, `eu.`, `ap.`, `global.`) prepended to the model ID. If a job fails with an access or model-not-found error, suggest adding the appropriate prefix.

**Known models (use ONLY these names and IDs):**

| Name | Model ID |
|------|----------|
| Nova Micro | `amazon.nova-micro-v1:0` |
| Nova Lite | `amazon.nova-lite-v1:0` |
| Nova Pro | `amazon.nova-pro-v1:0` |
| Nova 2 Lite | `amazon.nova-2-lite-v1:0` |
| Claude Haiku 4.5 | `anthropic.claude-haiku-4-5-20251001-v1:0` |
| Claude Sonnet 4.5 | `anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Claude Sonnet 4.6 | `anthropic.claude-sonnet-4-6` |
| Claude Opus 4.6 | `anthropic.claude-opus-4-6-v1` |
| Claude Opus 4.7 | `anthropic.claude-opus-4-7` |
| Llama 4 Maverick 17B | `meta.llama4-maverick-17b-instruct-v1:0` |
| Llama 4 Scout 17B | `meta.llama4-scout-17b-instruct-v1:0` |
| Mistral Large 3 | `mistral.mistral-large-3-675b-instruct` |
| DeepSeek-R1 | `deepseek.r1-v1:0` |
| DeepSeek V3.2 | `deepseek.v3.2` |

For the full list including additional providers, see `references/supported-models.md`.

**BAD — do not do this:**
```
Which model would you like to optimize for?
1. Nova 2 Lite
2. Claude Sonnet 4.5
3. Nova 2 Pro        ← hallucinated, doesn't exist
```

**GOOD — do this instead:**
```
Which model would you like to optimize for?
```
If the user says "I'm not sure", point them to multi-model comparison as the best way to evaluate, rather than recommending specific models.

### Step 3: Choose the Evaluation Method

The evaluation method directly steers how the optimizer rewrites the prompt — a vague evaluator produces vague improvements, while a precise one drives targeted gains. Ask the user about the nature of their task:

> Is this a task with **clear right/wrong answers** (structured extraction, classification, exact formats), or is it more **open-ended** (summarization, creative writing, conversational)?

**Decision guide:**

| Task Type | Recommended Method | Why |
|-----------|-------------------|-----|
| Structured extraction (JSON, key-value) | **Lambda evaluator** with deterministic metrics (ANLS*, exact match, F1) | Ground truth is unambiguous. Deterministic scoring gives precise, consistent signal. No judge subjectivity. |
| Classification / labeling | **Lambda evaluator** with accuracy/F1 | Right/wrong answers. No need for an LLM to judge. |
| Format compliance (dates, numbers, codes) | **Lambda evaluator** with exact match or regex | Binary correctness. |
| Summarization / paraphrasing | **LLM-as-a-judge** | Quality is subjective. Needs semantic understanding. |
| Creative / conversational | **LLM-as-a-judge** or **Steering criteria** | No single right answer. |
| Quick iteration / exploration | **Steering criteria** or **System default** | Low setup cost. Good for initial experiments. |

**Prefer 1–3 specific criteria over 5 vague ones.** Overlapping criteria dilute the optimization signal and produce vague rewrites.

**Key principle:** If you have ground truth and can write a function to score correctness, use a Lambda evaluator. It's faster (no judge inference cost), cheaper, deterministic, and gives the optimizer a tighter signal. Reserve LLM-as-a-judge for tasks where quality requires semantic judgment.

If the user needs a Lambda evaluator, see the **Deploying a Lambda Evaluator** section below for setup instructions.

### Step 4: Design the Evaluator Metrics (Lambda evaluator only)

Before writing any code, think carefully about which metrics best align with the user's task and goals. The scoring function is the optimization signal — if it measures the wrong thing, the optimizer will push in the wrong direction.

**Analyze the ground truth structure.** Look at the user's ground truth data and consider each field individually:

- **Which fields tolerate partial matches?** Names, addresses, and free-text descriptions may have minor spelling variations or formatting differences that shouldn't be penalized harshly. Use ANLS* (Average Normalized Levenshtein Similarity) or similar fuzzy metrics for these.
- **Which fields require exact correctness?** Account numbers, dates, monetary amounts, and classification labels have no room for "close enough." Use exact match for these.
- **Are there fields with known formats?** Dates, phone numbers, and currency values might need normalization before comparison (e.g., "$1,500.00" vs "1500.00" vs "1500").

**Design a hybrid metric when appropriate.** A single metric rarely fits all fields in a structured extraction task. The best evaluators often combine strategies:

```
Example: Invoice extraction
- Vendor name → ANLS* (tolerates minor OCR-like variations)
- Total amount → exact match after normalization (strip $, commas)
- Invoice date → exact match after date normalization
- PO number → exact match (no tolerance)
- Overall score → weighted average across fields
```

**Discuss the approach with the user.** Before implementing, briefly explain your proposed scoring strategy and ask if it aligns with their priorities. Some users may want to weight certain fields more heavily, or may have domain-specific tolerance rules you wouldn't know about.

**Keep the score continuous (0.0 to 1.0).** The optimizer converges better with granular scores than binary pass/fail. A per-field scoring approach naturally produces continuous values (e.g., 4 out of 5 fields correct = 0.8).

**Start from the template.** When writing the Lambda function, always start from `examples/lambda-evaluator-template.py`. This template has the correct `lambda_handler` with the exact event key names (`preds` and `golds`) that the service sends. Copy the template, then customize only the `compute_score` and `_score_single` functions with your scoring logic. Do NOT write the handler from scratch — the event key names are a common source of bugs.

**Always emit scores in the 0.0–1.0 range.** Use this convention in both Lambda evaluators and LLM-as-a-judge prompts. Mixing 0–100 and 0.0–1.0 across evaluators silently miscalibrates optimization across templates.

**Handle Markdown code fences in JSON output.** When the evaluator expects JSON structured output, some models wrap their JSON in Markdown code fences (e.g., ` ```json ... ``` `). Ask the user how to handle this:
- **Tolerant mode:** Strip code fences before parsing the JSON. This is forgiving of a common model behavior and focuses the optimization on content accuracy rather than formatting.
- **Strict mode:** Treat any response wrapped in code fences as a score of 0. This forces the optimizer to rewrite the prompt until the model produces clean JSON without fences.

The right choice depends on the downstream consumer. If the output feeds into a parser that handles fence-stripping, tolerant mode avoids penalizing otherwise-correct extractions. If the output goes directly into an API or pipeline that expects raw JSON, strict mode ensures the optimized prompt produces clean output.

### Step 5: Build the Samples File

Every workflow produces a `prompt-optimization/samples.json` file. This is the standard input to `prepare_dataset.py` in Step 6. How you create it depends on whether the task involves multimodal input (images/PDFs) or is text-only.

#### Multimodal samples (images/PDFs)

Use `build_multimodal_samples.py` to upload documents to S3 and generate the samples file:

```bash
python .kiro/skills/bedrock-advpo/scripts/build_multimodal_samples.py \
  --assets-dir path/to/documents \
  --bucket my-bucket \
  --s3-prefix advpo/documents \
  --output prompt-optimization/samples.json \
  --region us-east-1
```

Key options:
- `--no-ground-truth` — build samples without ground truth (no `referenceResponse`). Discovers all document files matching `--doc-ext` in the assets directory.
- `--doc-ext .png .jpg .tiff` — document file extension(s) to look for (default: `.png .jpg .jpeg .webp .gif`). Accepts multiple values for mixed-format directories.
- `--multimodal-type PDF` — set the multimodal type accordingly
- `--multimodal-name invoice_image` — customize the variable name
- `--skip-upload` — if files are already in S3
- `--gt-suffix -ground_truth.json` — customize ground truth file suffix
- `--input-variables vars.json` — add shared text variables to every sample
- `--parallel 10` — number of concurrent uploads (default: 10)

#### Text-only samples

For prompts with text variables and no multimodal input, write `samples.json` directly. No script is needed — just create the file based on whatever data the user provides (CSV, JSON, inline examples, etc.).

The format is a JSON array of sample objects. Each sample must include `inputVariables` as a list of single-key objects (one per template placeholder). `referenceResponse` is optional but recommended when ground truth is available.

**Example** — prompt template with `{{context}}` and `{{question}}` placeholders:

```json
[
  {
    "inputVariables": [
      {"context": "Returns are accepted within 30 days with original receipt."},
      {"question": "Can I return something I bought last week?"}
    ],
    "referenceResponse": "Yes, your purchase is within the 30-day return window."
  },
  {
    "inputVariables": [
      {"context": "Express shipping costs $12.99 and takes 2 business days."},
      {"question": "How fast is express shipping?"}
    ]
  }
]
```

Note: `referenceResponse` can be omitted for samples without ground truth (as shown in the second sample above). Without it, you cannot use a Lambda evaluator — use steering criteria or LLM-as-a-judge instead.

**Sample count and composition matter.** A representative dataset of 30–80 samples is the sweet spot — fewer than ~20 risks overfitting, and beyond ~80 you mostly add cost without much signal. The optimizer holds out a portion of your samples for evaluation of the optimized prompt, so include hard cases (ambiguous fields, edge formats, the failure modes you actually want fixed). A dataset dominated by trivial passing samples produces flat optimization curves — the optimizer learns most from your weakest examples.

### Step 6: Prepare the JSONL Dataset

Use `prepare_dataset.py` to validate and format the input dataset:

```bash
python .kiro/skills/bedrock-advpo/scripts/prepare_dataset.py \
  --output prompt-optimization/dataset.jsonl \
  --template-id "my-template-v1" \
  --prompt-template-file prompts/my-prompt.md \
  --samples prompt-optimization/samples.json \
  --lambda-arn "arn:aws:lambda:..." \
  --metric-label "extraction_accuracy"
```

**Evaluation methods** (choose ONE or omit all for system default):
1. Steering criteria: `--steering-criteria "ACCURATE" "CONCISE"`
2. LLM-as-a-judge: `--llmj-prompt-file ... --llmj-model ... --metric-label ...`
3. Lambda evaluator: `--lambda-arn "arn:..." --metric-label ...`
4. System default: omit all evaluation flags

Run `--help` for the full list of options including inline prompt strings and LLMJ configuration.

### Step 7: Upload Dataset to S3

```bash
aws s3 cp prompt-optimization/dataset.jsonl s3://my-bucket/advpo/input/dataset.jsonl --region us-east-1
```

The S3 bucket **must be in the same region** as the optimization job.

### Step 8: Create the Optimization Job

**Job naming:** The script automatically appends a short unique hex suffix (4 characters) to the job name to avoid naming conflicts with previous runs. Pass a descriptive base name (e.g., `check-extraction-nova2lite`) and the script handles uniqueness — no need to generate a suffix manually.

```bash
python .kiro/skills/bedrock-advpo/scripts/create_job.py \
  --job-name "my-optimization-job-a3f7" \
  --input-s3-uri "s3://my-bucket/advpo/input/dataset.jsonl" \
  --output-s3-uri "s3://my-bucket/advpo/output/" \
  --models "us.amazon.nova-2-lite-v1:0" \
  --region us-east-1 \
  --tags owner=my-alias
```

The script performs a **pre-flight model access check** before creating the job. Use `--skip-preflight` to bypass if needed.

Tags are passed as `key=value` pairs and applied directly to the optimization job at creation time. You can pass multiple tags: `--tags owner=schultkr project=check-extraction env=dev`.

For multi-model comparison:
```bash
--models "us.anthropic.claude-sonnet-4-5-20250929-v1:0" "us.amazon.nova-2-lite-v1:0"
```

### Step 9: Monitor Job Status

```bash
python .kiro/skills/bedrock-advpo/scripts/manage_job.py status \
  --job-arn "arn:aws:bedrock:us-east-1:123456789012:advanced-prompt-optimization-job/abc123" \
  --region us-east-1
```

Other commands:
- `list` — list all jobs
- `stop --job-arn ...` — stop a running job
- `delete --job-arns ...` — delete completed jobs

### Step 10: Parse and Display Results

```bash
python .kiro/skills/bedrock-advpo/scripts/parse_results.py \
  --job-arn "arn:aws:bedrock:..." \
  --output-s3-uri "s3://my-bucket/advpo/output/" \
  --region us-east-1
```

Options:
- `--verbose` — show full raw JSON per result
- `--json` — output raw JSONL
- `--save prompt-optimization/results.jsonl` — save raw results locally

**Presenting results to the user:** When you display results, always lead with the aggregate score improvement (original avg → optimized avg, with the delta). Show this *before* discussing how the prompt was changed. Users want to know "did it work?" before "what did it do?"

### Step 11: Extract the Optimized Prompt

After showing results, always offer to save the optimized prompt as a clean, ready-to-use file. Use `extract_prompt.py`:

```bash
python .kiro/skills/bedrock-advpo/scripts/extract_prompt.py \
  --results prompt-optimization/results.jsonl \
  --output prompts/my-prompt-optimized.md
```

Or directly from S3:
```bash
python .kiro/skills/bedrock-advpo/scripts/extract_prompt.py \
  --job-arn "arn:aws:bedrock:..." \
  --output-s3-uri "s3://my-bucket/advpo/output/" \
  --output prompts/my-prompt-optimized.md \
  --region us-east-1
```

Options:
- `--template-id "my-template"` — select a specific template (when results contain multiple)
- `--model "us.amazon.nova-2-lite-v1:0"` — select a specific model (when results contain multiple)

The script handles converting the service's escaped braces (`{{`/`}}`) back to normal braces for direct use.

## What to Expect from a Job

- **Runtime:** 15–20 minutes for a small single-model job; multi-model jobs scale roughly linearly with model count. Many templates × many samples can take hours.

- **Cost:** All inference is billed at standard Bedrock on-demand pricing. As a rough planning guide, expect on the order of 15–20 target-model invocations per sample per model, plus a smaller number of feedback and judge invocations. A 5-model × 100-sample job is meaningful spend — don't treat it like a free experiment.

- **Output prompts often look similar to the original.** The optimizer preserves sections that already work and rewrites only the parts that aren't pulling their weight. Judge success by the score delta in `parse_results.py`, not by how different the new prompt looks.

- **Cross-region inference profiles:** If a job fails with a model-not-found or access error, the model probably needs a `us.` / `eu.` / `ap.` / `global.` prefix. Confirm with `aws bedrock list-inference-profiles --region <region>` that the exact prefixed ID is available before retrying.

## Multimodal-Only Prompts

For use cases where the prompt processes a document/image with no text variables (e.g., extracting fields from a scanned check), the pattern is:

1. The prompt template has **no `{{placeholder}}` variables** — it's just the instruction text. The optimizer will rewrite the instruction text to optimize it for the target model.
2. Each sample **omits `inputVariables` entirely** (do NOT include an empty list or empty dict).
3. The document is provided via `inputVariablesMultimodal`.

Example samples.json entry:
```json
{
  "inputVariablesMultimodal": [
    {"check_image": {"type": "IMAGE", "s3Uri": "s3://bucket/path/check.png"}}
  ],
  "referenceResponse": "{\"field1\": \"value1\", \"field2\": \"value2\"}"
}
```

The `build_multimodal_samples.py` script handles this pattern automatically when pairing ground truth files with images.

## Deploying a Lambda Evaluator

Use `deploy_evaluator.py` to handle the full deployment lifecycle in a single command:

```bash
python .kiro/skills/bedrock-advpo/scripts/deploy_evaluator.py \
  --function-name advpo-check-evaluator \
  --source prompt-optimization/evaluator/lambda_function.py \
  --region us-east-1 \
  --profile admin-933 \
  --tags owner=schultkr
```

The script creates the IAM role (with Lambda + Bedrock trust), attaches the execution policy, waits for propagation, deploys the function, adds both required invoke permissions (Bedrock service + caller role), and verifies the function is Active.

Options: `--role-name` (custom role name), `--profile` (elevated access), `--tags` (key=value pairs), `--invoker-role` (ARN of an additional role to grant invoke access — use when the role creating optimization jobs differs from the role deploying the function).

**On failure:** Reports which step failed with the exact error, exits non-zero, and leaves partial resources in place for diagnosis. If the function or role already exists, it updates rather than failing.

**On success:** Prints a JSON summary with `function_arn`, `role_arn`, `function_name`, `role_name`, and `region`.

For detailed reference on the underlying IAM and Lambda requirements, see `references/deploying-lambda-evaluator.md`.

## Testing a Lambda Evaluator

Every time you write a Lambda evaluator function, you must also write a local test script that validates it before deployment. A broken evaluator silently produces bad scores, causing the optimizer to push in the wrong direction.

**Critical:** Always start your Lambda function from `examples/lambda-evaluator-template.py`. The template contains the correct `lambda_handler` with the exact event keys (`preds` and `golds`) that the service uses. Customize only the scoring logic — never rewrite the handler from scratch.

For full testing conventions, example structure, and requirements, read `references/testing-lambda-evaluator.md`.

## Lambda Evaluator Sandbox Restrictions

Advanced Prompt Optimization statically scans evaluator code before accepting it. The full list of blocked function names, blocked module imports, and approved third-party libraries is documented in the `SANDBOX RESTRICTIONS` section of `examples/lambda-evaluator-template.py`. Always start from that template — it is the authoritative reference for what is and isn't allowed.

## Example LLMJ Prompts

The `examples/` directory contains ready-to-use LLM-as-a-judge prompts: `llmj-structured-extraction.md`, `llmj-classification.md`, and `llmj-summarization.md`. Use with `--llmj-prompt-file`.

## Dependencies

- Python 3.10+
- `boto3` — AWS SDK
- AWS CLI (for `build_multimodal_samples.py` S3 uploads)

## Supported Regions

us-east-1, us-east-2, us-west-2, ca-central-1, sa-east-1, eu-west-1, eu-west-2, eu-central-1, eu-central-2, ap-south-1, ap-northeast-1, ap-northeast-2, ap-southeast-1, ap-southeast-2

## Quotas

| Quota | Limit |
|-------|-------|
| Concurrent jobs | 20 per account per region |
| Input file size | 50 MB |
| Templates per job | 10 |
| Evaluation samples per template | 100 |
| Text variables per template | 20 |
| Multimodal files per sample | 2 |
| Models per job | 5 |
| Steering criteria per template | 5 |

## Available Judge Models (for LLM-as-a-judge)

- `anthropic.claude-opus-4-6-v1`
- `anthropic.claude-sonnet-4-6`
- `anthropic.claude-sonnet-4-5-20250929-v1:0`

These are the models supported as the `customLLMJModelId` in the dataset. The default judge (when no custom LLMJ is specified) is Claude Sonnet 4.6.

## Input Dataset Schema

For the full JSONL schema, field rules, and common mistakes to avoid, read `references/dataset-schema.md`. Consult it when constructing or debugging dataset files.

## Important

- **Jobs are asynchronous.** A single-template job with few samples takes 15–20 minutes. Many templates with many samples can take hours.
- **Costs are inference-based.** All model invocations run in your account at standard Bedrock on-demand pricing. There is no separate service charge.
- **S3 bucket must be in the same region as the job.**
- **Cross-region inference** may be used internally for evaluation and rewriting.
- **Model access must be enabled** in your account for all target models. The `create_job.py` script checks this before submitting.
