# Requirements Document

## Introduction

A lightweight Python-based eval framework that replaces the current `agent-skills-eval` (npm) + LiteLLM proxy setup. The framework runs behavioral evaluations against AI agent skills by invoking Claude Code or Kiro CLI in headless mode, then grading responses using either deterministic Python checks or an LLM judge on Amazon Bedrock.

## Glossary

- **Eval_Runner**: The top-level Python CLI that orchestrates eval execution, dispatching prompts to agent backends and collecting responses.
- **Agent_Backend**: A pluggable interface for sending prompts to an AI agent and receiving text responses. Implementations include Claude Code headless and Kiro CLI headless.
- **Eval_Case**: A single test case consisting of a prompt, optional context (skill path), and one or more grading criteria.
- **Grader**: A component that evaluates an agent response against defined criteria. Two types exist: deterministic (Python function) and LLM judge (Bedrock model call).
- **Deterministic_Grader**: A Python function that programmatically checks an agent response and returns a pass/fail result with optional reasoning.
- **LLM_Judge_Grader**: A grader that sends the agent response plus assertions to an Amazon Bedrock model for evaluation.
- **Eval_Config**: A YAML configuration file that defines which backend to use, model settings, concurrency, and output paths.
- **Eval_Result**: The structured output of a single eval case execution, containing pass/fail status, grader reasoning, timing, and the raw agent response.

## Requirements

### Requirement 1: Claude Code Headless Backend

**User Story:** As a skill developer, I want to run evals against Claude Code in headless mode, so that I can test how my skill behaves in the Claude Code agent environment.

#### Acceptance Criteria

1. WHEN an eval is configured with the Claude Code backend, THE Eval_Runner SHALL invoke Claude Code using the `--print` flag with the eval case prompt passed as a positional argument to the CLI command.
2. WHEN a skill path is specified in the eval configuration, THE Agent_Backend SHALL set the working directory for the Claude Code process to the skill path so that Claude Code discovers and loads the skill via standard skill directory conventions.
3. WHEN Claude Code returns a response with exit code 0, THE Agent_Backend SHALL capture the complete stdout output and pass it to the configured Grader.
4. IF Claude Code fails to produce a response within the configured timeout (default: 120 seconds, minimum: 10 seconds, maximum: 600 seconds), THEN THE Agent_Backend SHALL terminate the Claude Code process and mark the eval case as an error with the timeout duration in the Eval_Result.
5. IF Claude Code exits with a non-zero exit code, THEN THE Agent_Backend SHALL mark the eval case as an error and include the exit code and any stderr output in the Eval_Result.
6. IF the specified skill path does not exist or is not a valid directory, THEN THE Agent_Backend SHALL mark the eval case as an error with a message indicating the invalid skill path before attempting invocation.

### Requirement 2: Kiro CLI Headless Backend

**User Story:** As a skill developer, I want to run evals against the Kiro CLI in headless mode, so that I can test how my skill behaves in the Kiro agent environment.

#### Acceptance Criteria

1. WHEN an eval is configured with the Kiro CLI backend, THE Eval_Runner SHALL invoke the Kiro CLI using the `--acp` flag with the eval case prompt as input.
2. WHEN a skill path is specified in the eval configuration, THE Agent_Backend SHALL set the working directory to the skill's parent directory before invoking the Kiro CLI so the skill is discoverable during inference.
3. WHEN the Kiro CLI returns a response, THE Agent_Backend SHALL capture the complete text content from stdout and pass it to the configured Grader.
4. IF the Kiro CLI fails to produce a response within the configured timeout (default: 120 seconds, minimum: 10 seconds, maximum: 600 seconds), THEN THE Agent_Backend SHALL terminate the Kiro CLI process and mark the eval case as an error with the timeout duration in the result.
5. IF the Kiro CLI executable is not found on the system PATH, THEN THE Agent_Backend SHALL mark the eval case as an error with a message indicating the CLI is not installed or not accessible.

### Requirement 3: Deterministic Python Grading

**User Story:** As a skill developer, I want to write Python functions that programmatically check agent responses, so that I can create fast, reproducible, and cost-free evaluations for behaviors with clear pass/fail criteria.

#### Acceptance Criteria

1. WHEN an eval case specifies a deterministic grader via a Python dotted-path reference (e.g., `module.function_name`) in the eval configuration, THE Eval_Runner SHALL import and call the referenced Python function, passing the agent response text and the expected_output string (if defined) as arguments.
2. THE Deterministic_Grader function SHALL return a dictionary containing a boolean `passed` field and an optional `explanation` string field of at most 1024 characters.
3. WHEN multiple deterministic checks are defined for a single eval case, THE Eval_Runner SHALL execute all checks and report individual pass/fail results per check, regardless of whether earlier checks passed or failed.
4. IF a deterministic grader function raises an exception, THEN THE Eval_Runner SHALL mark that check as failed and include the first 512 characters of the exception message in the result.
5. IF a deterministic grader function does not return within 30 seconds, THEN THE Eval_Runner SHALL terminate the function execution, mark that check as failed, and include an explanation indicating a timeout occurred.

### Requirement 4: LLM Judge Grading via Amazon Bedrock

**User Story:** As a skill developer, I want to use an LLM on Amazon Bedrock as a judge for subjective or nuanced assertions, so that I can evaluate behaviors that are difficult to check programmatically.

#### Acceptance Criteria

1. WHEN an eval case specifies an LLM judge grader, THE Eval_Runner SHALL send the agent response and the assertion text to the configured Bedrock model for evaluation by constructing a prompt that instructs the judge to return a structured verdict containing a boolean pass/fail decision and a reasoning explanation.
2. THE LLM_Judge_Grader SHALL use the Amazon Bedrock Converse API to invoke the judge model.
3. WHEN the judge model returns its evaluation, THE LLM_Judge_Grader SHALL parse the response to extract a boolean pass/fail result and the judge's reasoning text.
4. THE Eval_Config SHALL allow specifying the judge model ID, AWS region, and inference parameters including temperature (value between 0.0 and 1.0).
5. IF the Bedrock API call fails, THEN THE LLM_Judge_Grader SHALL mark the assertion as an error and include the API error message in the result.
6. IF the judge model response cannot be parsed into a pass/fail verdict, THEN THE LLM_Judge_Grader SHALL mark the assertion as an error and include the unparseable response text in the result.
7. IF the Bedrock API call does not return a response within the timeout duration specified in the Eval_Config, THEN THE LLM_Judge_Grader SHALL mark the assertion as an error with a message indicating the timeout was exceeded.

### Requirement 5: Eval Configuration

**User Story:** As a skill developer, I want to configure eval runs through a YAML file, so that I can define backend selection, model parameters, and output settings in a declarative way.

#### Acceptance Criteria

1. THE Eval_Runner SHALL read configuration from a YAML file specified via the `--config` CLI argument.
2. IF no `--config` argument is provided, THEN THE Eval_Runner SHALL look for a file named `agent-skills-eval.yaml` in the current working directory.
3. THE Eval_Config SHALL support specifying the agent backend type (Claude Code or Kiro CLI).
4. THE Eval_Config SHALL support specifying the path to eval case definitions (JSON file).
5. THE Eval_Config SHALL support specifying the judge model ID and AWS region for LLM judge grading.
6. THE Eval_Config SHALL support specifying a timeout duration for agent backend calls as an integer value in seconds, with a minimum of 1 second and a maximum of 600 seconds.
7. THE Eval_Config SHALL support specifying concurrency as an integer between 1 and 32 representing the number of parallel eval cases to run.
8. WHEN a required configuration field is missing, THE Eval_Runner SHALL exit with a non-zero exit code and print an error message to stderr identifying the missing field by name.
9. WHEN a CLI flag is provided that corresponds to a configuration field, THE Eval_Runner SHALL use the CLI flag value, overriding the YAML file value for that field.

### Requirement 6: Eval Case Definition Format

**User Story:** As a skill developer, I want to define eval cases in a JSON file with prompts and grading criteria, so that I can maintain a suite of behavioral tests for my skill.

#### Acceptance Criteria

1. THE Eval_Runner SHALL read eval cases from a JSON file whose path is specified in the Eval_Config, expecting a top-level object containing a `skill_name` string and an `evals` array of Eval_Case objects.
2. Each Eval_Case SHALL contain an `id` field (lowercase alphanumeric string with hyphens, maximum 64 characters), a human-readable `name` string (maximum 120 characters), a `prompt` string, an optional `expected_output` string describing the ideal response, and an `assertions` array containing 1 to 20 assertion strings.
3. Each assertion string SHALL be a natural-language statement evaluated by the LLM judge grader, describing a pass/fail condition for the system response. WHERE a deterministic grader is configured, THE grading criterion SHALL specify a Python function reference in dotted-module notation (e.g., `module.function`).
4. THE Eval_Runner SHALL validate the eval case file on load and report any structural errors — including invalid JSON syntax, missing required fields (`id`, `name`, `prompt`, `assertions`), field type mismatches, or empty `assertions` arrays — before execution begins, identifying the offending eval case `id` or array index in the error output.
5. WHEN the eval case file references a deterministic grader function that cannot be imported, THE Eval_Runner SHALL report the import error including the function reference that failed and skip that eval case while continuing to execute remaining cases.
6. THE Eval_Runner SHALL reject the eval case file with a validation error IF any two Eval_Case objects share the same `id` value.

### Requirement 7: Result Output and Reporting

**User Story:** As a skill developer, I want structured output from eval runs, so that I can track pass rates over time and diagnose failures.

#### Acceptance Criteria

1. WHEN an eval run completes, THE Eval_Runner SHALL write a JSON results file containing for each eval case: a pass/fail/error status, grader reasoning text, timing in milliseconds, and the raw agent response.
2. WHEN an eval run completes, THE Eval_Runner SHALL print a summary to stdout showing total cases run, pass count, fail count, error count, and overall pass rate as a decimal value between 0.0 and 1.0.
3. IF any eval case has a status of "fail" or "error", THEN THE Eval_Runner SHALL exit with exit code 1.
4. WHEN an eval run completes with all cases passing, THE Eval_Runner SHALL exit with exit code 0.
5. THE Eval_Runner SHALL organize output files in a directory named with an ISO 8601 timestamp (YYYY-MM-DDTHH-MM-SS) within the output path specified in the eval configuration file.
6. IF the configured output path does not exist, THEN THE Eval_Runner SHALL create the directory and any necessary parent directories before writing results.
7. IF the configured output path is not writable, THEN THE Eval_Runner SHALL exit with a non-zero exit code and print an error message indicating the path and reason for failure.

### Requirement 8: CLI Interface

**User Story:** As a skill developer, I want to invoke the eval framework from the command line, so that I can run evals manually or integrate them into CI scripts.

#### Acceptance Criteria

1. THE Eval_Runner SHALL provide a CLI entry point invocable via `python -m cli_eval`.
2. THE Eval_Runner SHALL accept a required `--config` argument specifying the path to the YAML configuration file.
3. IF the `--config` argument is not provided or the specified file does not exist, THEN THE Eval_Runner SHALL exit with a non-zero exit code and print an error message indicating the missing or invalid config path.
4. THE Eval_Runner SHALL accept an optional `--filter` argument to run only eval cases whose ID contains the given string as a substring (case-sensitive).
5. IF a `--filter` is provided and no eval cases match, THEN THE Eval_Runner SHALL exit with a zero exit code and print a message indicating that no cases matched the filter.
6. THE Eval_Runner SHALL accept an optional `--verbose` flag that enables logging of full agent responses and grader reasoning to stdout.
7. WHEN invoked with `--help`, THE Eval_Runner SHALL display usage information describing all available arguments.
