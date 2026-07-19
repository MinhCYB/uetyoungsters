# Student Companion Engine V1 Scenario Matrix

All timestamps and identifiers come from deterministic fixtures or explicit
factory values. The CLI and pytest suite execute the same scenario functions in
`phase1_demo/engine_scenarios.py`.

| ID | Input condition | Expected behavior | Warning | Plan / outcome | Test |
|---|---|---|---|---|---|
| S01 | Weak trigonometry, good data reasoning, Data activity completed | Full T0→T1 flow remains compatible | Existing market warning allowed | 20+25 minutes; meaningful improvement; next Economics | `test_engine_scenario[S01]` |
| S02 | `exam_week=true` | Career exploration is deferred | None required | Academic-only and within budget | `test_engine_scenario[S02]` |
| S03 | Self-report absent | Academic analysis still runs; no inferred interest evidence | `optional_data_missing` | Normal gap analysis | `test_engine_scenario[S03]` |
| S04 | Teacher observations absent | Estimate uses remaining sources with lower diversity/count confidence | `optional_data_missing` | Pipeline continues | `test_engine_scenario[S04]` |
| S05 | High assessment, low record and weakness observation | Conflict reduces confidence | `conflicting_evidence` | No strong conclusion from conflict | `test_engine_scenario[S05]` |
| S06 | Equal normalized pre/post scores | Trend is stable | None required | `no_meaningful_change`; no false improving trend | `test_engine_scenario[S06]` |
| S07 | Delta in partial band | Academic gap shrinks but remains open | None required | `partial_improvement` | `test_engine_scenario[S07]` |
| S08 | Posttest lower than baseline | Supportive remediation selected | None required | `regression`; trigonometry foundation next step | `test_engine_scenario[S08]` |
| S09 | Activity incomplete | No activity evidence/outcome is invented | None required | Exploration gap remains | `test_engine_scenario[S09]` |
| S10 | Three interests; only Data explored | Decision remains open | None required | Economics is next feasible unexplored activity | `test_engine_scenario[S10]` |
| S11 | Market sample below five | Market remains context only | `small_market_sample` | Ability and planning continue | `test_engine_scenario[S11]` |
| S12 | Unknown career group | Academic analysis does not crash | `unknown_career_group` | No unsupported career task | `test_engine_scenario[S12]` |
| S13 | Data activity already completed | Immediate repetition is excluded | None required | Another eligible direction is considered | `test_engine_scenario[S13]` |
| S14 | Pretest 4/10, posttest 14/20 | Both scales normalize before comparison | No scale warning | Values compare as 0.4→0.7 | `test_engine_scenario[S14]` |
| S15 | Zero max score | Model rejects invalid scale | Validation error | No engine execution | `test_engine_scenario[S15]` |
| S16 | Posttest without matching baseline | Baseline is not inferred | `baseline_not_found` | No fabricated assessment outcome | `test_engine_scenario[S16]` |
| S17 | Follow-up from T0 | T0 remains byte-identical | None required | New snapshot points to T0 | `test_engine_scenario[S17]` |
| S18 | Same request executed twice | Responses are identical; IDs and warnings are unique | No duplicates | Idempotent deterministic output | `test_engine_scenario[S18]` |

Additional invariant suites cover source weighting, confidence bounds, internal
priority scoring, seven-group activity catalog completeness, frozen schema
fingerprints, legacy JSON parsing, local demo compatibility, and a deterministic
30-variation batch smoke.
