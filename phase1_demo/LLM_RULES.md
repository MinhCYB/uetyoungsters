# Student Companion LLM V1 Rules

## Audited boundary

The public Companion contract remains `1.0.0`; the three
`StudentCompanionFacade` signatures are unchanged. The content layer is an
internal, optional layer after Engine V1 and is never required for analysis,
planning, outcomes, or next-step selection.

Engine-owned immutable decisions:

- `skill_id`, career group, activity type and difficulty constraint;
- gap type, priority, target and confidence;
- task duration and weekly total;
- assessment timing, score and maximum score;
- outcome, improvement and next step;
- market signal and any career decision.

LLM/provider-generated content is limited to:

- student-friendly objectives and step wording;
- instructions, hints and explanations;
- reassessment question wording within an engine specification;
- concise student/teacher-facing summaries.

Generated content must never change scores, confidence, gap type, priority,
time, outcome, career conclusions, or market signals. It must not expose raw
evidence IDs, private profile metadata, prompts, secrets, or chain of thought.

## Audit findings

- `PlanTask` already owns skill/career references and exact minutes;
  `WeeklyPlan` enforces the total budget.
- `AbilityEstimate`, `Gap`, and `OutcomeEvaluation` provide constraints but are
  not recalculated by the content layer.
- The activity catalog covers seven career groups and provides safe titles,
  descriptions, rubrics and reflection questions.
- The public facade is stateless and remains untouched by this layer.
- The local dependency-free HTTP demo has no content endpoints; integration is
  optional and is not required for the content core.
- `core/shared/llm_client.py` is an empty vendor-oriented stub. Vendor packages
  are listed only in the separate core service requirements, not in the active
  demo runtime. It cannot be safely reused for deterministic offline tests.

Therefore V1 uses a provider-neutral port, deterministic TemplateProvider,
scriptable FakeLLMProvider, and a fail-closed ExistingProviderAdapter
placeholder. No live provider is claimed or invoked.

## Generation and fallback flow

The orchestrator builds a minimal versioned prompt, calls the injected provider,
parses JSON, validates the Pydantic schema, then enforces request-specific and
safety invariants. A provider gets one initial attempt and at most one retry.
Malformed JSON, schema errors, invariant violations, timeouts, and provider
exceptions fall back to TemplateProvider. Fallback success is returned with
`content_mode=template_fallback` and internal warning codes; raw exceptions are
not exposed.

Content IDs are hashes of caller request data and validated content. No UUID,
randomness, or current timestamp is used.

## Prompt privacy

Prompts include only language, grade, the selected task/specification, and the
minimum answer context needed by the use case. They exclude tenant/teacher IDs,
full profiles, database metadata, market internals, raw evidence IDs, secrets,
and unrelated observations.

## Safety rules

Student-facing text is rejected when it contains evidence/technical IDs,
judgmental language, absolute career verdicts, guaranteed future claims,
medical diagnosis, unsafe instructions, requests for unnecessary personal
information, score changes, or specialist SQL/Python/portfolio work not
requested by the engine.

## Production limitations

- Generated reassessment questions require teacher or curated question-bank
  validation before production use; V1 validates orchestration and structure,
  not complete mathematical correctness.
- Generic fallback questions for skills outside trigonometry and data reasoning
  are explicitly marked as template content, not expert-approved content.
- No live model provider, production prompt store, moderation service, API,
  database, queue, RAG, fine-tuning, or frontend integration is included.
