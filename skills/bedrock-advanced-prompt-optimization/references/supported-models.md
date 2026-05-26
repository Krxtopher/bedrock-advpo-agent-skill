# Suggested Target Models for AdvPO

AdvPO works with any text-generation model available through Amazon Bedrock. This list contains commonly-used models that make good optimization targets. When suggesting models to the user, draw from this list and use the exact model IDs shown — do not invent or guess model IDs.

> **This list may not be exhaustive.** New models are added to Bedrock regularly. If the user asks about a model not listed here, or if you want to confirm what's currently available in their account and region, run:
> ```bash
> aws bedrock list-foundation-models --region <region> --query "modelSummaries[?contains(outputModalities, 'TEXT')].{id:modelId, name:modelName, provider:providerName}" --output table
> ```

## Cross-Region Inference Prefixes

Many models require a cross-region inference prefix to be invoked. When using these models as AdvPO targets, prepend the appropriate prefix to the model ID:

| Prefix | Meaning |
|--------|---------|
| `us.` | US regions |
| `eu.` | EU regions |
| `ap.` | Asia-Pacific regions |
| `global.` | Global (any available region) |

Example: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`

Cross-region model IDs are valid for AdvPO's `--models` parameter and are often required for newer models that aren't available as single-region endpoints. If a job fails with an access error, try adding the appropriate prefix.

## Amazon

| Model | Model ID |
|-------|----------|
| Nova 2 Lite | `amazon.nova-2-lite-v1:0` |
| Nova Pro | `amazon.nova-pro-v1:0` |
| Nova Lite | `amazon.nova-lite-v1:0` |
| Nova Micro | `amazon.nova-micro-v1:0` |

## Anthropic

| Model | Model ID |
|-------|----------|
| Claude Opus 4.7 | `anthropic.claude-opus-4-7` |
| Claude Opus 4.6 | `anthropic.claude-opus-4-6-v1` |
| Claude Sonnet 4.6 | `anthropic.claude-sonnet-4-6` |
| Claude Sonnet 4.5 | `anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Claude Haiku 4.5 | `anthropic.claude-haiku-4-5-20251001-v1:0` |

## Meta

| Model | Model ID |
|-------|----------|
| Llama 4 Maverick 17B Instruct | `meta.llama4-maverick-17b-instruct-v1:0` |
| Llama 4 Scout 17B Instruct | `meta.llama4-scout-17b-instruct-v1:0` |
| Llama 3.3 70B Instruct | `meta.llama3-3-70b-instruct-v1:0` |

## Mistral AI

| Model | Model ID |
|-------|----------|
| Mistral Large 3 | `mistral.mistral-large-3-675b-instruct` |
| Devstral 2 123B | `mistral.devstral-2-123b` |
| Pixtral Large | `mistral.pixtral-large-2502-v1:0` |
| Magistral Small 2509 | `mistral.magistral-small-2509` |

## DeepSeek

| Model | Model ID |
|-------|----------|
| DeepSeek V3.2 | `deepseek.v3.2` |
| DeepSeek-R1 | `deepseek.r1-v1:0` |

## OpenAI

| Model | Model ID |
|-------|----------|
| GPT OSS 120B | `openai.gpt-oss-120b-1:0` |
| GPT OSS 20B | `openai.gpt-oss-20b-1:0` |

## Google

| Model | Model ID |
|-------|----------|
| Gemma 3 27B | `google.gemma-3-27b-it` |
| Gemma 3 12B | `google.gemma-3-12b-it` |

## Qwen

| Model | Model ID |
|-------|----------|
| Qwen3 Coder Next | `qwen.qwen3-coder-next` |
| Qwen3 VL 235B A22B | `qwen.qwen3-vl-235b-a22b` |
| Qwen3 32B | `qwen.qwen3-32b-v1:0` |

## NVIDIA

| Model | Model ID |
|-------|----------|
| Nemotron Super 3 120B | `nvidia.nemotron-super-3-120b` |
| Nemotron Nano 3 30B | `nvidia.nemotron-nano-3-30b` |

## Writer

| Model | Model ID |
|-------|----------|
| Palmyra X5 | `writer.palmyra-x5-v1:0` |

## MiniMax

| Model | Model ID |
|-------|----------|
| MiniMax M2.5 | `minimax.minimax-m2.5` |

## Moonshot AI

| Model | Model ID |
|-------|----------|
| Kimi K2.5 | `moonshotai.kimi-k2.5` |
| Kimi K2 Thinking | `moonshot.kimi-k2-thinking` |

## Z.AI

| Model | Model ID |
|-------|----------|
| GLM 5 | `zai.glm-5` |
