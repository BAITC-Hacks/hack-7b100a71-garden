# Career Quest frontend

React frontend connected to the FastAPI backend and the deterministic recommendation engine. The approved HTTP contract is [FRONTEND_API_CONTRACT.md](../docs/FRONTEND_API_CONTRACT.md); verification and remaining limitations are recorded in the [Phase 2 audit](../docs/integration-phase2-audit.md).

## Run locally

Use Node.js **22.12 or newer**, pnpm **11.25.0**, and Python **3.11 or newer** for the backend.

From the repository root, prepare a local `.env` using the root `.env.example` if one does not already exist. For identity-aware access, set `CAREER_QUEST_AUTH_DISABLED=false`, configure your own `HR_API_TOKEN`, and set `EMPLOYEE_TOKENS_JSON` to a JSON object mapping each employee token to its employee ID. Keep these values on the backend.

```sh
./run.sh
```

The script installs backend dependencies and starts FastAPI at `http://127.0.0.1:8000`. It loads the root `.env`. Backend CORS defaults allow `http://127.0.0.1:5173` and `http://localhost:5173`; configure `CAREER_QUEST_CORS_ORIGINS` if using another frontend origin. Runtime state defaults to `.runtime/state.json`; use one backend worker.

In a separate terminal, from `frontend/`:

```sh
pnpm install --frozen-lockfile
pnpm dev
```

Open the URL printed by Vite, normally `http://127.0.0.1:5173`. Real API mode is the default. Optional `frontend/.env.local` settings follow the public [`.env.example`](.env.example):

```dotenv
VITE_API_MODE=real
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Vite variables are included in the browser bundle. Never put bearer tokens, OpenAI keys, or other secrets in them. Real mode never falls back to fixture data when the backend fails.

## Identity and navigation

The entry screen asks for an opaque access token and its assigned workspace: HR, or Employee with an employee ID. These fields provide navigation context; the backend independently validates the token and authorizes every request. There is no invented `/auth/login` or `/me` endpoint, and choosing HR does not grant HR access.

Tokens remain in tab memory only. Reloading or selecting **Change identity** clears the session; identity changes cancel pending queries and clear cached data.

- Employees open their own `/employees/:employeeId` workspace directly. They never request the HR-only employee directory or see its selector.
- HR opens `/`, can search the employee directory and select any authorized profile, and uses `/hr` for analytics and dataset management.
- Unauthorized, forbidden, missing-profile, configuration, backend-unavailable, loading, and empty states are distinct. A production static host must route application URLs to `index.html`.

## Employee and HR flows

The employee dashboard shows identity, effective current skills, current role/grade, explicit or resolved career target, target requirements, critical gaps, readiness, participation history, and up to three recommendations in backend order. The career path displays only the current and target positions supported by these responses.

Recommendations retain server explanations, projections, factors, raw evidence, and version. `no_next_grade`, `target_satisfied`, and `no_eligible_recommendations` are normal outcomes. UI text is currently English; supplied recommendation explanations render in **kk, ru, or en**, according to the employee preference. The frontend never calls OpenAI; optional enrichment and deterministic fallback remain on the backend.

Completion sends `POST /activities/{event_id}/complete` with one idempotency key per action. A retry reuses that key. When active assignments require a specific attempt, the selected `record_id` is supplied. After the backend receipt, profile, history, recommendations, and relevant HR queries are invalidated and refreshed. The frontend does not award local gains or recalculate readiness; mismatched profile/recommendation versions are shown as a synchronization state.

HR analytics use only the defined backend aggregates. Skill gaps relate to current role/grade, and partial or unavailable recommendation coverage stays visibly partial or unavailable. There is no employee performance ranking.

The HR upload panel supports `append` and `replace`, validation errors and counts, then atomic upload. Multipart fields are `employees_file`, `activity_history_file`, `events_file`, and `skills_file`; replacement requires all four. Changing the selection or mode invalidates the previous validation result. There is no `validationId`. Successful upload refreshes snapshot-dependent queries so HR can open new profiles immediately; employee-token mappings for new users are configured separately on the backend.

## Data boundaries

- `src/types/transport.ts` mirrors backend JSON; `src/types/domain.ts` contains frontend view models.
- `src/services/httpApi.ts` maps transport to views, attaches bearer authorization, reads envelopes, follows pagination, checks snapshot versions, preserves error status/code/details, and honors cancellation.
- `src/services/api.ts` selects the adapter; hooks manage React Query loading, caching, completion, and refresh.
- Displayed current skills come from `effective_skills`. Assessment baseline `employee.skills` remains separate.
- Readiness uses the backend's 0–1 value and is only formatted as a percentage. Rank, score, gaps, critical flags, explanation text, and projected changes remain backend-owned. Raw recommendation evidence is retained.

For isolated UI development, explicitly set `VITE_API_MODE=mock`. This uses synthetic fixtures and needs no backend token. Development-only `?mockScenario=empty`, `error`, `retry`, `slow`, or `career-error` can exercise presentation states. Mock completion and dataset mutations remain unavailable; use real mode for the hackathon demo.

## Verification

From `frontend/`:

```sh
pnpm test
pnpm typecheck
pnpm lint
pnpm build
pnpm preview
```

Phase 2 verification: **120 frontend tests** and the unchanged **425 backend/recommendation/AI/integration tests** pass; frontend build, typecheck, and lint pass. Component tests and API-adapter tests are separate from actual browser verification.

Actual browser checks covered E0001 completion and progress refresh, E0004 cross-role completion, E0006/E0018 normal empty recommendation states, HR analytics, validation/upload of a new employee through append mode, and a four-file replace in the disposable runtime. See the [Phase 2 audit](../docs/integration-phase2-audit.md) for exact values, evidence, and scope.
