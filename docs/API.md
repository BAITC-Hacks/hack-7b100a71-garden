# Career Quest API 0.2.0

Frontend integration contract for Adilet. Local base URL: `http://127.0.0.1:8000`. Interactive documentation: `/docs`; machine-readable schema: `/openapi.json`. The final integration payload contract and actual backend examples are in [FRONTEND_API_CONTRACT.md](FRONTEND_API_CONTRACT.md) and [integration-phase1-results.json](integration-phase1-results.json).

## Changes from the first backend version

Successful responses now contain `data`. Lists contain an array in `data` and pagination in `meta`; the old top-level `items` and `total` fields are gone. List requests return at most 50 records by default. Dataset replacement uses `?mode=replace`, replacing `replace_existing=true`. Completion requires an `Idempotency-Key` header. Runtime changes persist in Supabase when `DATABASE_URL` is configured, or in the local snapshot when a state path is configured.

## Authentication and access

Send `Authorization: Bearer YOUR_TOKEN` on every data request. `/health`, `/docs` and `/openapi.json` are public. Swagger's **Authorize** button accepts the token.

The server maps each configured employee token to one employee ID. An employee may read their own profile, history and recommendations, complete their own activities, and read catalogs. An HR token may access every employee, employee lists, analytics and dataset imports. Headers such as `X-Role` do not grant access.

Authentication is enabled by default. Missing or invalid credentials return `401`; a valid request format against an unconfigured authentication service returns `503`. `CAREER_QUEST_AUTH_DISABLED=true` explicitly grants HR access for the local synthetic-data demo. Employee tokens are configured as a JSON token-to-employee map in `EMPLOYEE_TOKENS_JSON`; the HR token is `HR_API_TOKEN`.

## Response conventions

Calendar dates use `YYYY-MM-DD`; runtime `completed_at` is an ISO timestamp with UTC offset. IDs are opaque strings. Missing skill keys mean level zero. Optional domain values can be `null`; clients must preserve this distinction from zero.

```ts
type SnapshotMeta = {
  version: number;        // Runtime dataset version, initially 1
  as_of_date: string;     // Dataset date, initially "2026-10-01"
};
type PageMeta = SnapshotMeta & { total: number; offset: number; limit: number };
type Success<T> = { data: T; meta?: SnapshotMeta | PageMeta };
type Failure = {
  error: { code: string; message: string; details: unknown[] };
};
```

All successful endpoints return HTTP `200`. Lookup endpoints include snapshot metadata. Completion, dataset actions and recommendations return the fields described below inside `data`; they do not include top-level `meta`. Health includes its snapshot fields inside `data`.

List endpoints accept `offset=0` and `limit=50`, with `offset >= 0` and `1 <= limit <= 500`. `meta.total` is the number matching the filters before pagination. Out-of-range offsets return an empty array. Employee/event/skill/profile lists follow dataset order; history is ordered by date and record ID, oldest first. Fetch further pages while `offset + data.length < meta.total`. If `meta.version` changes between requests, restart pagination to read a consistent dataset.

Example public health response for the untouched starter dataset:

```json
{
  "data": {
    "status": "ok",
    "version": 1,
    "as_of_date": "2026-10-01",
    "counts": {
      "employees": 200,
      "skills": 60,
      "role_profiles": 32,
      "events": 40,
      "history": 2743
    }
  }
}
```

Counts and versions can change after imports or completion. Do not hard-code dataset sizes or employee/event IDs.

## Routes and read payloads

| Method and path | Access | `data` |
| --- | --- | --- |
| `GET /health` | Public | Status, version, dataset date and counts |
| `GET /employees` | HR | `Employee[]`, with page metadata |
| `GET /employees/{employee_id}` | Self or HR | `{employee, role_profile, effective_skills}` |
| `GET /employees/{employee_id}/history` | Self or HR | `ActivityRecord[]`, with page metadata |
| `GET /employees/{employee_id}/recommendations` | Self or HR | Full engine result with explanations; see below |
| `GET /events` | Employee or HR | `Event[]`, with page metadata |
| `GET /events/{event_id}` | Employee or HR | One event |
| `GET /skills` | Employee or HR | `Skill[]`, with page metadata |
| `GET /skills/{skill_id}` | Employee or HR | One skill |
| `GET /role-profiles` | Employee or HR | `RoleProfile[]`, with page metadata |
| `GET /role-profiles/{role}/{grade}` | Employee or HR | One role and grade profile; URL-encode the role |
| `GET /hr/analytics` | HR | Aggregate analytics described below |
| `POST /activities/{event_id}/complete` | Self or HR | Completion receipt described below |
| `POST /datasets/validate` | HR | Validation result; does not change live data |
| `POST /datasets/upload` | HR | Import receipt; atomically publishes valid data |

Additional filters use exact, case-sensitive matches:

| List | Optional query parameters |
| --- | --- |
| `/employees` | `department`, `role`, `grade` |
| `/events` | `role`, `grade`, `type`, `format`, `mandatory=true` or `false` |
| `/skills` | `type`, `category` |
| `/role-profiles` | `role`, `grade` |

Grades are `Junior`, `Middle`, `Senior`, `Lead`. Event types are `compliance`, `onboarding`, `course`, `workshop`, `mentoring`, `certification`, `meetup`. Event formats are `online`, `offline`, `self_paced`; skill types are `hard` and `soft`. Catalog filters describe the event audience and characteristics; they do not check an employee's completed events or prerequisites.

The OpenAPI domain schemas preserve the official dataset fields:

- `Employee`: identity, name, department, role, grade, nullable manager, hire date, tenure, work format, preferred language, nullable career goal, assessed `skills`, and `last_review_date`.
- Profile payload: `employee` is the assessed profile; `role_profile` describes its current role and grade; `effective_skills` includes applicable completed activities. Use `effective_skills` for the current progress display. A skill key absent from this map is zero.
- `RoleProfile`: `role`, `grade`, `required_skills`, `critical_skills`.
- `Event`: `event_id`, `title`, `description`, `type`, `format`, `duration_hours`, `mandatory`, `target_roles`, `target_grades`, `develops_skills`, `prerequisites`, `upcoming_sessions`.
- `Skill`: `skill_id`, `name`, `type`, `category`, `description`.
- `ActivityRecord`: `record_id`, `employee_id`, `event_id`, `date`, nullable `due_date`, `status`, `completion_pct`, nullable `score` and `feedback_rating`, `assigned_by`, and optional nullable `completed_on`, `completed_at`, `runtime_sequence`. New runtime completions contain an exact UTC `completed_at`, logical snapshot date `completed_on`, and persisted operation order `runtime_sequence`. Historical records are not assigned invented timestamps. `date` preserves the original enrollment or session date when completing an existing assignment.

Example catalog request:

```bash
curl --get 'http://127.0.0.1:8000/events' \
  -H "Authorization: Bearer $CAREER_TOKEN" \
  --data-urlencode 'role=Backend Engineer' \
  --data-urlencode 'grade=Junior' \
  --data-urlencode 'mandatory=false' \
  --data-urlencode 'limit=100'
```

## Activity completion and retry handling

```http
POST /activities/EV_005/complete
Authorization: Bearer YOUR_TOKEN
Idempotency-Key: 24a22cc5-8b88-4df4-b5ac-ce1ee9aef257
Content-Type: application/json

{"employee_id":"E0001","score":85,"feedback_rating":5}
```

`E0001` and `EV_005` are a usable example in the untouched official dataset; existing runtime changes may make the event unavailable.

The JSON body accepts only these fields:

| Field | Required | Value |
| --- | --- | --- |
| `employee_id` | Yes | Nonempty string |
| `record_id` | No | Nonempty string identifying an existing active or overdue assignment; default `null` |
| `score` | No | Integer `0..100` or `null`; supported for course, certification and compliance events |
| `feedback_rating` | No | Integer `1..5` or `null` |

Numbers must be JSON integers; strings and booleans are rejected. Additional fields are rejected. The idempotency key must contain 1–128 characters and cannot be blank. Generate it once per intended completion, then reuse it with the same request body for retries, including after a network timeout. Reusing a key for different input returns `409 idempotency_conflict`.

The success payload is:

```ts
type CompletionReceipt = {
  activity: ActivityRecord;
  effective_skills: Record<string, number>;
  skill_changes: Array<{
    skill_id: string;
    before: number;
    after: number;
    gain: number;        // Actual change, possibly 0
    event_gain: number;  // Catalog gain
    max_level: number;
  }>;
  version: number;
  replayed: boolean;
};
```

A retry returns the saved original receipt with `replayed=true`, without creating another completion or incrementing the version. Its `version` is the version of that original completion; refresh the profile and history for current state.

When exactly one active or overdue assignment exists, omitting `record_id` selects it. Multiple such assignments return `409 ambiguous_activity`; send the intended record ID from history. Mandatory activities require an existing assignment. New voluntary participation checks the attained current grade and effective prerequisites. The audience may match the current role or an explicit destination role; destination-only admission also reuses the engine's deterministic eligibility check. Most development events cannot be completed twice. The recurring club `EV_036` permits later sessions, with one completion per dataset date.

Completion records both the dataset's logical `as_of_date` in `completed_on` and the actual UTC clock instant in `completed_at`. Persisted transaction order resolves same-day/timestamp ties. Profile, completion and recommendations share the engine's reconstruction function; gains are capped by `max_level` and never reduce an already higher skill. The assessed `employee.skills` remain the last-review baseline. The exact review-day and two-clock rules are documented in [the final contract](FRONTEND_API_CONTRACT.md). Refresh profile, history and recommendations after completion; the receipt does not calculate readiness separately.

## Dataset validation and import

Both endpoints accept `multipart/form-data` and query parameter `mode=append` or `mode=replace`. The default is `append`.

| Multipart field | Official content |
| --- | --- |
| `employees_file` | `employees.json`, including its metadata and `employees` array |
| `activity_history_file` | `activity_history.csv`, including its header row |
| `events_file` | `events.json`, including metadata and the event array |
| `skills_file` | `skills.json`, including metadata, proficiency scale, skills and role profiles |

At least one nonempty file is required. The default combined file-content limit is 10 MiB, configurable with `CAREER_QUEST_UPLOAD_MAX_BYTES`. Oversized uploads return `413 upload_too_large`.

Append accepts new employee profiles, new history records, or both. Existing catalogs resolve references. IDs must be new; append does not overwrite profiles or activity records. Employee-document metadata must match the active dataset. Catalog changes require replacement. Replace requires all four files and clears earlier runtime completion receipts. Every candidate is validated as a complete dataset before publication; failure leaves live data unchanged.

```bash
curl 'http://127.0.0.1:8000/datasets/validate?mode=append' \
  -H "Authorization: Bearer $CAREER_TOKEN" \
  -F 'employees_file=@new_employees.json;type=application/json' \
  -F 'activity_history_file=@new_activity_history.csv;type=text/csv'
```

To publish the same candidate, send the same multipart request to `/datasets/upload?mode=append`. In browser code, use `FormData` and let `fetch` set the multipart `Content-Type` boundary.

Validation returns HTTP `200` for both valid and invalid dataset content:

```ts
type DatasetValidation = {
  valid: boolean;
  counts: Record<"employees" | "skills" | "role_profiles" | "events" | "history", number> | {};
  errors: Array<{code: string; location: string; message: string}>;
  mode: "append" | "replace";
  version: number; // The live version against which the candidate was checked
};
```

For valid content, `counts` describes the full candidate after merging. Invalid content returns `{}` for counts and a list of errors. Missing files, empty files, an invalid mode or a size violation are request errors (`422` or `413`), even on `/validate`.

Upload returns `data: {uploaded: true, mode, counts, version}` on success. Invalid dataset content returns HTTP `422` with `error.code="invalid_dataset"` and issues in `error.details`. Validation does not reserve a dataset version; upload revalidates against the live state. Refresh cached profiles, history, recommendations and HR analytics after a successful import.

## Recommendations and HR analytics

The route is connected to the real provider by default. One authorized repository view supplies the original assessment baseline, all role profiles, the full event catalog, full employee history and snapshot date. Completion and dataset import invalidate the versioned cache. No recommendation request reads a fixed local dataset path or substitutes projected skills for the baseline.

The response is `{data: result}` with the full engine result and the repository `version`:

```ts
type RecommendationResult = {
  employee_id: string;
  as_of: string;
  version: number;
  status: "ok" | "no_next_grade" | "no_eligible_recommendations"
        | "target_satisfied" | "invalid_target_requirements";
  target: {role: string; grade: string; source: "career_goal" | "next_grade"} | null;
  career_readiness: ReadinessResult | null;
  skill_gaps: SkillGap[];
  career_state: CareerState;
  candidate_count: number;       // Eligible pool before top-3 selection
  recommendation_count: number;
  blocked_summary: BlockedSummary | null;
  recommendations: Array<{
    rank: number;               // Keep this order; no frontend ranking
    event_id: string;
    title: string;
    score: number;              // 0..1, retain precision
    factors: Record<string, {
      raw: number; normalized: number; weight: number; contribution: number;
    }>;
    scoring_evidence: ScoringEvidence;
    simulation: EventSimulation;
    evidence: CandidateEvidence;
    history_signals: HistorySignals;
    explanation?: Explanation;
  }>;
  explanation_summary?: Explanation;
  explanation_meta?: ExplanationMetadata;
};
```

The referenced nested structures are the existing [engine contracts](../backend/recommendation/contracts.py) and [explanation contracts](../backend/ai/contracts.py); the [final frontend contract](FRONTEND_API_CONTRACT.md) describes their UI mappings. `career_readiness.current` is a fraction, not a percentage or promotion promise. Simulation preserves gaps, actual gains, requirements closed and readiness before/after. Audience evidence distinguishes `current_role`, `target_role` and `both`, always using attained current grade for admission. Normalized factors accompany raw evidence; do not replace them with the retired `reason`/`skill_changes` transport fields.

Explanations use the employee's `preferred_language` (`kk`, `ru`, `en`). OpenAI is optional and can only enrich phrasing of existing facts; it cannot select, reorder, rescore or modify recommendations. A missing `OPENAI_API_KEY`, API failure, timeout or unsupported output produces deterministic explanations and HTTP `200`. Inspect `explanation_meta.provider_status` for the fallback reason. Never put an API key in frontend code.

`no_next_grade`, `no_eligible_recommendations`, `target_satisfied` and `invalid_target_requirements` are HTTP `200` results with empty recommendations and structured explanations. They are not infrastructure errors. Explicitly disabling the provider with `create_app(recommendation_provider=None)` still returns `503 recommendation_unavailable`.

The backend validates the full shape, counts/ranks and repository references while retaining the exact engine JSON values. Invalid provider output returns `502`; its timeout returns `504`; a snapshot change during generation returns `409 dataset_changed`. The frontend may retry the latter. After route authorization, the service creates one view and passes it through adapter and response validation.

HR analytics returns `employee_count`, `gap_basis`, `common_skill_gaps`, `employees_without_next_step`, `activity_participation` and `participation_summary`. Skill gaps compare effective skills against the **current** role and grade. Each common-gap row contains `skill_id`, `skill_name`, `category`, `employee_count`, `total_levels_missing`, and `critical_employee_count`.

Participation includes all six statuses: `completed`, `in_progress`, `dropped`, `no_show`, `declined`, `overdue`. `participation_summary` contains `total_records`, `participating_employees` and separate `voluntary` and `mandatory` status maps.

`employees_without_next_step` contains `{available, count, evaluated_count, pending_count, complete}`. An optional fast deterministic `provider.coverage(view)` hook can supply a complete summary. Otherwise it describes recommendation results already computed for the current dataset version. Until results exist, `count` is `null`. The count is partial while `complete=false`; `pending_count` records how many employees are still unevaluated. HR requests never generate AI explanations for every employee. See [the integration contract](INTEGRATION.md).

## Handling errors in the frontend

| HTTP status | Expected client action |
| --- | --- |
| `401` | Supply a valid token; the response includes `WWW-Authenticate: Bearer` |
| `403` | Show that the operation is unavailable for this identity |
| `404` | Show that the requested employee, event, skill or profile does not exist |
| `409` | Resolve the stated conflict; inspect `error.code` before retrying |
| `413` | Reduce the combined upload size |
| `422` | Display field or dataset errors from `error.details` |
| `502`, `503`, `504` | Show service unavailability or timeout with a retry option |

Request validation errors use `code="invalid_request"`; detail items include a location such as `body.score` or `header.Idempotency-Key`, a message and a code. Parse failures and unknown routes also use the `error` envelope. Display `error.message` as the summary and preserve details for field-level feedback.
