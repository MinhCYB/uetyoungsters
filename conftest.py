"""Repository-wide test configuration."""

import os


# Automated tests are deterministic and never call the live AI Worker or Gemini.
os.environ["COMPANION_LLM_MODE"] = "template"
