"""Shared pytest configuration and fixtures for skill script tests."""

import sys
from pathlib import Path

# Add the skill scripts and examples directories to the import path so tests
# can import them directly.
SKILL_ROOT = Path(__file__).parent.parent / "skills" / "bedrock-advanced-prompt-optimization"
SCRIPTS_DIR = SKILL_ROOT / "scripts"
EXAMPLES_DIR = SKILL_ROOT / "examples"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(EXAMPLES_DIR))
