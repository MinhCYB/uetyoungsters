# Student Companion E2E integration

## Compatibility audit

The repository has two authoritative contracts at different boundaries, not two competing core contracts:

- `backend-api/modules/candidate/analysis_contracts.py` validates the versioned source `StudentProfilePayload` and wraps it as the candidate module's `InitialAnalysisRequest` or `FollowupEvaluationRequest`.
- `phase1_demo/student_companion/contracts/` is public contract `1.0.0` consumed by `StudentCompanionFacade`. The facade signatures remain unchanged.
- `backend-api/modules/companion/service.py` is the profile-to-core adapter. It always validates the source payload through `to_initial_analysis_request(...)` or `to_followup_evaluation_request(...)` before constructing the existing facade request class.
- `backend-api/modules/companion/presentation.py` is a presentation DTO mapper, not a third engine contract.

### Concrete mismatches and resolutions

| Source profile | Core/public contract | Integration resolution |
| --- | --- | --- |
| Nested `profile` wrapper | Flat facade request collections | Validate the wrapper first, then map its validated collections. |
| Lowercase `skill_*` IDs | Uppercase canonical Engine V1 IDs | An explicit `SKILL_MAP` is isolated in the adapter. |
| `purpose`, `submitted_at` | `assessment_type`, `completed_at` | Preserve the purpose value and use `submitted_at`, falling back to `started_at`. |
| One observation can contain many `skill_ids` | One core observation per `skill_id` | Split deterministically with a stable suffix; preserve student and observation time. |
| No weekly-minute field in initial profile | `StudentProfile.weekly_available_minutes` is required | Golden-path policy uses 45 minutes. This is demo policy, not production persistence or an Engine rule. |
| Initial profile has no career self-report | Exploration/decision require career groups | The demo adapter supplies the two existing Engine V1 groups, Data/AI and Economics. Week 3 derives the same groups from profile interests. |
| Data-literacy fixture has no exact Engine V1 academic activity slot | The only existing 20-minute academic activity targets `SKILL_TRIG_TRANSFORMATION` | Adapter-only compatibility calibration maps the fixture measure into that existing canonical slot. The same factor is applied to pretest and posttest; no Engine threshold, activity, rule, or facade code changes. This is the main known demo limitation. |
| Source activity contains a skill but no career group or interest before/after | Core career activity requires these fields | Map the known clean-data activity to the existing Data/AI micro-experience and use deterministic demo interest anchors. |
| Core gap reason contains evidence IDs | UI must not expose evidence internals | Presentation emits a safe description by gap type and never forwards `reason`, `evidence_ids`, `source_reference`, priority scores, or thresholds. |
| Core warnings use `warning_code`, `message`, `affected_field` | Frontend requires code/severity/title/message/action | Presentation maps to the frontend shape and omits affected technical paths. |
| Core plan is a single weekly budget and task list | Frontend requires `duration_weeks`, `weekly_plan`, progress and activities | Presentation wraps the unchanged task list as one 45-minute week. |
| Core follow-up exposes outcomes and snapshots | Frontend requires baseline, progress, before/after and next steps | Presentation maps each outcome to a common 0–100 scale and forwards the baseline analysis ID held by the store. |

`gap_type` remains the business vocabulary `academic`, `exploration`, or `decision`. The optional, separate `gap_dimension` is `knowledge`, `experience`, or `null`; a decision gap is never relabeled as a skill or experience gap.

## Identity, time, version and lineage

- `student_id` is copied from the validated source student into every core parent/child record. Pydantic validators reject inconsistent child IDs before mapping.
- Request timestamps come from the fixture's `generated_at`; snapshot and plan timestamps come from the facade request metadata. No current timestamp is generated.
- Source `profile_version` is retained in store records, presentation DTOs, and facade metadata as `taxonomy_version=profile-vN` because public contract 1.0.0 has no dedicated profile-version field.
- `analysis_id`, request IDs and content IDs are deterministic SHA-256-derived IDs. No random UUID is used.
- Follow-up loads the stored baseline analysis and passes its real `snapshot` into `StudentCompanionFacade.evaluate_followup(...)`.

## Frontend presentation fields

`frontend/src/contracts/responseAdapter.js` requires common contract/version, response kind, request/student/time, title, warnings and next steps. Initial analysis additionally requires ability and gap collections; plan requires plan ID, duration, progress and weekly plan; follow-up requires baseline analysis ID, progress and before/after. The backend presentation mapper supplies display names for every user-facing canonical ID, plus plan activities, outcomes and updated gaps used by the golden path.

Fallback market mode is presented only as “Dữ liệu dự phòng cho demo”. TemplateProvider content is presented as “Nội dung mẫu an toàn”, never as AI-generated content.

## Runtime flow and state

1. `POST /api/companion/analyze` loads the selected source profile, validates candidate contract, maps to public core contract, calls `facade.analyze`, stores the response, and returns presentation DTO.
2. `POST /api/companion/plan` loads the stored analysis snapshot, calls `facade.generate_plan`, stores the plan, and returns presentation DTO.
3. Content endpoints call the existing `StudentCompanionContentOrchestrator` with `TemplateProvider`; engine-selected task ID, skill, career group and minutes are unchanged.
4. `POST /api/companion/followup` validates week-3 profile, loads baseline snapshot, maps the same pre/post skill consistently, calls `facade.evaluate_followup`, and returns before/after plus next step.
5. `POST /api/companion/reset` clears only the process-local demo store. This store is explicitly not production persistence.

Invalid transitions return structured errors: `analysis_not_found`, `plan_not_found`, `baseline_not_found`, `invalid_transition`, or `contract_validation_failed`. Raw tracebacks are not returned by these routes.

## Local demo mode without PostgreSQL

From the repository root, start the backend in PowerShell with database initialization disabled:

```powershell
$env:SKIP_DB_INIT = "1"
python -m uvicorn main:app --app-dir backend-api --host 127.0.0.1 --port 8000
```

When the demo session is finished, remove the environment variable:

```powershell
Remove-Item Env:SKIP_DB_INIT
```

Without `SKIP_DB_INIT=1`, startup keeps the normal behavior: it calls `init_db()` and reports PostgreSQL connection failures. The Companion analyze, plan, and follow-up demo path uses fixtures plus the process-local in-memory store and remains available when database initialization is skipped.

## Exporter hygiene

`export_contract_examples(output_dir)` already supports a caller-owned output directory. Integration tests now export only to `tmp_path`, assert all six files, assert byte determinism over two runs, and verify canonical examples remain byte-identical. CLI default behavior remains unchanged.

## Known limitations

- The compatibility calibration and default career groups are demo bridge policy forced by missing source fields and the fixed Engine V1 catalog. A production profile contract should carry canonical competency mapping, career interests, and weekly budget explicitly.
- State is process-local and resettable; no database, authentication, RBAC, queue, scheduler, deployment, RAG, external LLM, or production persistence is added.
- Normal backend startup still expects its pre-existing PostgreSQL database. Local demo mode can explicitly skip only database initialization with `SKIP_DB_INIT=1`; Companion itself needs no network, database, or API key.
