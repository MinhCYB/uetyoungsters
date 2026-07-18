# AI Worker architecture update

`ai-worker-service` is now a generic synchronous LLM gateway exposed through
`POST /infer`. It does not contain assessment, candidate, recommendation, CV,
essay, or roadmap business logic.

The configured provider is Gemini. It reads `GEMINI_API_KEY`, `DEFAULT_MODEL`,
`DEFAULT_MAX_TOKENS`, and `REQUEST_TIMEOUT_SECONDS` from the environment. All
four settings are required; service configuration has no hardcoded fallback.

Older architecture notes allowing AI Worker to write directly to assessment
responses or `professional_profiles.parsed_data` are obsolete. The gateway does
not connect to Postgres or Redis. Each caller builds its own prompt, validates
the raw response, and persists the result in its own database.
