# Student Companion Engine Rules V1

## Compatibility boundary

Public contract `1.0.0` and the signatures of `StudentCompanionFacade.analyze`,
`generate_plan`, and `evaluate_followup` are frozen. Internal scores and policy
configuration are deliberately absent from public JSON.

The original demo must continue to produce a 45-minute plan consisting of 20
minutes of trigonometry practice and a 25-minute Data/AI micro-activity. After
the supplied follow-up, its next career step remains Economics.

## Audit before hardening

| Area | Existing rule | Existing limitation | V1 hardening |
|---|---|---|---|
| Evidence | Normalize scores to `[0, 1]`; stable IDs; source weights | Confidence was only mean effective source weight | Add sparse-source, diversity, agreement, and conflict policy |
| Ability | Weighted mean by source reliability | Strong disagreement did not reduce confidence | Deterministic conflict penalty; bounded confidence |
| Gaps | Academic threshold; unexplored career groups; decision gap until all interests explored | Academic priority was only gap size; exploration always high | Internal traceable priority scores and confidence-aware bands |
| Planner | Academic high gap first; career activity when not exam week; budget enforced | Catalog covered two career groups | Seven career groups; completed activity is not repeated |
| Outcome | Normalized before/after delta with four statuses | Missing baseline was silently skipped | Structured baseline warning; valid differing scales remain comparable |
| Market | Read-only provider with local fallback | Unknown group caused facade failure | Warning and partial analysis instead of crash |
| Warnings | Optional input, sparse aggregate, small market sample | Rules lived in facade and did not inspect conflict/low confidence | Pure deterministic warning engine using `ContractWarning` |

## Evidence and confidence

Configuration version: `confidence-1.0.0`.

Source reliability remains, in descending order: assessment `1.0`, academic
record `0.9`, teacher observation `0.8`, activity result `0.8`, self-report
`0.4`. Ability level remains the reliability-weighted mean.

Confidence starts from total effective source reliability divided by the
minimum evidence count, capped at one. A single self-report receives a
sparse-evidence factor. Repeated evidence from only one source type receives no
diversity benefit and a configurable penalty. When the normalized range exceeds
the conflict threshold, confidence is multiplied by an agreement factor. The
final value is rounded and clamped to `[0, 1]`.

Recency weighting is intentionally deferred: timestamps exist, but no product
policy defines a valid decay horizon and adding one would unexpectedly change
the existing demo.

## Warnings

The pure warning engine supports:

- `insufficient_evidence`
- `small_market_sample`
- `optional_data_missing`
- `conflicting_evidence`
- `low_confidence_estimate`
- `unknown_career_group`
- `stale_profile_version` when both versions are available
- `baseline_not_found`
- `assessment_scale_mismatch` through explicit scale validation; invalid
  zero/overflow scales are rejected by domain models, while valid 4/10 and
  14/20 values are normalized and compared

Warnings are sorted, de-duplicated by `(warning_code, affected_field)`, and do
not place evidence IDs in display messages.

## Gap priority

Academic priority uses an internal score:

`gap_size × confidence_factor × prerequisite_importance × school_priority × feasibility_factor`

Low-confidence estimates cannot create a high-priority conclusion. Current
curriculum skills receive the school factor; exam week increases it. A feasible
catalog activity supplies the feasibility factor. Scores map deterministically
to public `low`, `medium`, or `high` bands.

Exploration priority considers declared interest, whether a qualifying activity
has been completed, and whether a fitting activity exists inside the weekly
budget. Decision gaps remain open until every considered direction has a
qualifying experience; trying only one direction never closes the gap. Market
demand is context only and never enters priority scoring.

## Planner and activity selection

During exam week only academic tasks are eligible. At other times the planner
selects a feasible high-priority academic task first, then the first feasible
unexplored career activity in the student's declared order. Completed activity
IDs are excluded. Activities are stable, versioned, suitable for high-school
students, include rubric dimensions and reflection questions, and require no
specialist programming or portfolio work.

## Outcomes and snapshots

Assessment outcomes compare normalized values, so different positive scales
are valid. Missing matching baselines are never inferred. Thresholds remain:
regression at `<= -0.05`, no meaningful change below `0.05`, partial improvement
below `0.20`, and meaningful improvement from `0.20`.

All IDs, ordering, plans, warnings, snapshots, and outputs are deterministic.
Facade calls do not mutate request objects or previous snapshots.

## Limitations

- No recency decay, production profile adapter, persistence, API, UI, auth, or
  external service is included.
- Profile staleness can only be evaluated when an adapter supplies both current
  and expected versions to the internal helper; contract `1.0.0` has no such
  comparison field.
- Partial plan completion is represented by the activity results supplied by an
  adapter; no new public progress field is introduced in V1.
