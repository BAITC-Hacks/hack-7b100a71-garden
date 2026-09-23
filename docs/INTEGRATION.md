# Backend integration contract

Bekarys's backend owns validated data access, completion, persistence and HTTP authorization. Zhanibek's engine owns career targets, eligibility, scoring/ranking, readiness, simulation and explanations. Adilet's frontend consumes the [HTTP API](API.md) and [final frontend contract](FRONTEND_API_CONTRACT.md). Actual integrated HTTP results are recorded in [integration-phase1-results.json](integration-phase1-results.json).

## Provider wiring

`create_app()` connects `backend.integrations.recommendation_provider.RecommendationProvider` by default. The existing endpoint calls it through `RecommendationService`:

```text
authorization → one RepositoryView → provider
→ deterministic recommend() → explanation enrichment
→ full response validation → HTTP envelope
```

A custom provider may still be injected using `create_app(recommendation_provider=provider)`. Its `recommend(employee_id, view)` can be synchronous or asynchronous and may return a dictionary or validated `RecommendationResult`. Explicit `recommendation_provider=None` represents an unavailable engine and returns HTTP 503; legitimate empty results remain HTTP 200.

The factory performs no dataset IO at import. Loading and runtime-state recovery occur during FastAPI lifespan. Use `TestClient` as a context manager in tests.

The default provider requests optional OpenAI enrichment. `OPENAI_API_KEY` is read only through the isolated explanation layer; missing credentials, provider failures, timeouts and unsupported responses fall back to deterministic text. `RecommendationProvider(use_openai=False)` disables external enrichment explicitly. Languages come from the employee profile. The engine's ranking, scores and evidence never depend on OpenAI availability.

## Full result validation

The source schemas remain `backend/recommendation/contracts.py` and `backend/ai/contracts.py`. The backend transport reuses their TypedDict annotations, with a local compatibility conversion for Pydantic on Python below 3.12. It does not introduce competing employee models or nested recommendation schemas. Validation preserves the original JSON values, including raw numerical evidence, and rejects unexpected fields.

The result retains:

- `employee_id`, `as_of`, `status`, target with `source`;
- `career_readiness`, `skill_gaps`, the complete `career_state`;
- candidate and recommendation counts, `blocked_summary`;
- each recommendation's `rank`, `event_id`, `title`, `score`, `factors`, `scoring_evidence`, `simulation`, `evidence`, `history_signals`;
- optional recommendation `explanation`, top-level `explanation_summary` and `explanation_meta`.

The preliminary `reason`, evidence-list and top-level numeric-readiness DTO is retired. Current readiness is `career_readiness.current`, when available. It describes weighted target-requirement coverage, not guaranteed promotion.

The service validates the requested employee and snapshot date, existing target profile, distinct known voluntary events and simulated skill references. It does not change engine decisions. The HTTP result adds repository `version`. Default provider timeout is nine seconds: timeout returns 504, invalid/failed output 502, and a snapshot mutation during calculation 409. Results cache by employee and dataset version; completion and import invalidate the old version.

## One snapshot and one reconstruction

After route authorization, the service creates one detached `RepositoryView`. The provider uses that exact view for every input and validation, and never calls a loader or opens `data/`:

```python
employee = view.get_employee(employee_id)  # Original assessment baseline
profiles = view.get_all_role_profiles()
events = view.get_all_events()
history = view.get_employee_history(employee_id)  # Full history, no HTTP pagination
runtime_ids = view.get_runtime_completion_ids()
as_of = view.as_of_date
```

Pydantic domain objects are converted with `model_dump(mode="json")`. `history_for_engine(history, runtime_ids)` adapts the trusted runtime chronology before calling `recommend(...)`. The employee's `preferred_language` then selects explanation language. Read methods return defensive copies; all IDs and catalog sizes remain dataset-driven, including after append or replace.

**Never assign `view.get_effective_skills()` to `employee.skills` before invoking the engine.** Its input is always assessment baseline plus full history. Effective skills are derived once during reconstruction, with no gain written back to baseline.

`RepositoryView.get_effective_skills` delegates to the same engine reconstruction through the same history adapter. Profile and completion therefore share skill semantics with recommendations. There is no independent readiness calculation inside completion.

New runtime completions preserve an exact UTC `completed_at`, logical snapshot date `completed_on`, and persisted `runtime_sequence`. Only the backend transaction supplies trusted runtime context. Legacy date-only records retain approximation semantics and acquire no invented timestamp. See [the final temporal contract](FRONTEND_API_CONTRACT.md) for review-day handling and the deliberate distinction between snapshot time and actual wall time.

## Completion and refresh

The existing completion endpoint requires an `Idempotency-Key` for one intended operation. Reuse the same key and payload for retry; mismatched input returns 409. An exact retry returns the original receipt with `replayed=true`, including after restart, without replaying gain or increasing the version.

New participation checks attained grade and prerequisites. Destination-role-only admission reuses deterministic engine eligibility, so cross-role recommendations can be completed without granting arbitrary events or weakening identity checks. Mandatory activities still require an existing assignment.

After completion, fetch profile, history and recommendations again. The receipt provides actual skill changes and its version; the next recommendation request recalculates effective skills, readiness, admission, ranking and explanations from the new persisted history. Assessed skills and `last_review_date` remain unchanged.

Runtime state is separate from source data. Use one application worker; transactions serialize requests within that process. Full dataset replacement intentionally discards prior runtime order and idempotency receipts. Append/replace publish validated snapshots atomically, and the provider reads the active version on subsequent requests.

## Fast HR coverage

An injected provider can optionally supply synchronous `coverage(view)` returning `evaluated_count` and `without_next_step_count`, with `0 <= without_next_step_count <= evaluated_count <= employee_count`. The hook must be fast, deterministic and independent of AI generation; its result is cached per dataset version.

The default provider uses cached employee results instead. Until one result exists, coverage `count` is null. `evaluated_count`, `pending_count` and `complete` distinguish partial coverage from a full calculation. An invalid optional hook falls back to cached results. An HR request never calls recommendations or OpenAI for every employee.
