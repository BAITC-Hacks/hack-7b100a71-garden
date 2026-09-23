# Backend integration contract

The backend owns validated data access, activity completion, state persistence and HTTP authorization. Zhanibek's engine owns career targets, recommendation eligibility/ranking, readiness, simulation explanations and AI output. Adilet's frontend consumes the [HTTP contract](API.md).

## Register the engine

Create the application with `create_app(recommendation_provider=your_engine)`, importing the factory from `backend.main`. The provider implements `recommend(employee_id, view)` synchronously or asynchronously. It returns `RecommendationResult` from `backend.integrations.recommendations`, or a dictionary matching that model.

The application factory does no dataset IO at module import. Dataset initialization and runtime-state recovery happen in FastAPI lifespan. Tests using the factory should use `TestClient` as a context manager.

A result has these fields:

- `employee_id`: the requested employee.
- `target`: optional `{role, grade}`; the pair must exist in the supplied profiles.
- `career_readiness`: optional number from 0 to 1, calculated by the engine.
- `recommendations`: zero to three items, each with a distinct existing voluntary `event_id`, a `reason`, and at least two pieces of `evidence`.
- `notes`: optional list of strings, such as an explanation for an empty result.

Each evidence item is `{factor, explanation, values?}`. `values` is an optional JSON object for the facts supporting the explanation. An item can also contain `skill_changes: [{skill_id, before, after}]`. The backend validates this response shape and references; it supplies no replacement ranking algorithm.

The API response adds the dataset `version`. The default recommendation time limit is nine seconds. A missing provider returns `503`, timeout `504`, invalid/failed provider output `502`, and a dataset mutation during generation `409` so the client can retry. Successful output is cached per employee and dataset version. Completion and upload increment the version, invalidating the old cache.

## Read one consistent snapshot

`view` is a detached `RepositoryView` with `version` and `as_of_date`. Use the same view throughout one calculation. Its methods are:

```python
view.get_employee(employee_id)          # Employee or None
view.get_all_employees()                # list[Employee]
view.get_skill(skill_id)                # Skill or None
view.get_all_skills()                   # list[Skill]
view.get_role_profile(role, grade)      # RoleProfile or None
view.get_all_role_profiles()            # list[RoleProfile]
view.get_event(event_id)                # Event or None
view.get_all_events()                   # list[Event]
view.get_employee_history(employee_id)  # list[ActivityRecord]
view.get_all_history()                  # list[ActivityRecord]
view.get_effective_skills(employee_id)  # dict[skill_id, level]
```

Read methods return defensive copies. Editing a returned model cannot modify the live repository. Lists contain all imported profiles; do not rely on original IDs or counts.

`get_effective_skills` is the shared skill projection. It starts at the assessed profile, then applies relevant completed events using `max(current, min(current + gain, max_level))`. Missing keys mean zero. Do not apply historical gains a second time to this result.

The engine can inspect raw history for no-shows, refusals, completion rate and other evidence. Historical self-paced rows do not contain exact completion dates; see [dataset notes](DATASET_NOTES.md). New completions retain their original session/enrollment `date`, set `completed_on`, and preserve real operation order even for several completions on one day.

## Fast HR coverage

Optionally implement a synchronous `coverage(view)` method returning:

```json
{
  "evaluated_count": 200,
  "without_next_step_count": 17
}
```

These are illustrative counts; calculate them from the supplied snapshot. The summary must be deterministic, fast, and independent of AI text generation. Bounds must satisfy `0 <= without_next_step_count <= evaluated_count <= employee_count`. It is cached for the current dataset version.

If no summary hook is supplied, HR reports coverage from already cached employee recommendations: `count` is null until at least one employee has been evaluated, and `evaluated_count`, `pending_count` and `complete` expose the coverage. A failing or invalid summary hook falls back to this known cache. The backend never obtains HR coverage by calling `recommend` for every employee.

## Mutation and frontend refresh

The completion endpoint requires an `Idempotency-Key` chosen by the frontend for a single operation. Reuse it only when retrying the identical request; use a new value for a new action. A mismatch returns `409`. An exact retry returns the original response with `replayed=true`, even after a restart.

After completion, refresh the employee profile and recommendations. The completion response already contains skill changes and the new version. The base `employee.skills` assessment remains unchanged. Import is transactional, so a frontend never observes half a dataset.

Runtime state is persisted separately from source data. The process uses one worker; atomic transactions protect simultaneous requests in that process. A full replacement deliberately discards the old runtime completion order and idempotency receipts.
