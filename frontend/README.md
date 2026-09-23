# Career Quest frontend

Final frontend checkpoint: employee development, aggregate HR insights, dataset management, and a centralized real API adapter. Frontend work belongs on `feat/adilet` and stays in `frontend/`. Recommendation, readiness, skill-gap, validation, and analytics business logic remain backend-owned.

The adapter targets the [team contract at `3a90322`](https://github.com/BAITC-Hacks/hack-7b100a71-garden/blob/3a90322a728f592888929903cb4a9f671d048b3e/docs/FRONTEND_API_CONTRACT.md). Contract tests use representative transport responses; they do not establish that a deployed backend is reachable or configured.

## Setup and verification

Use Node.js 22.12 or newer and pnpm 11.25.0. From this directory:

```sh
pnpm install --frozen-lockfile
pnpm dev
```

Open the URL printed by Vite. Copy `.env.example` to `.env.local` to select an adapter, then restart Vite after changing environment settings.

```dotenv
# Default: isolated synthetic demo, no backend calls.
VITE_API_MODE=mock
VITE_API_BASE_URL=
```

For the externally running backend, set `VITE_API_MODE=real` and `VITE_API_BASE_URL` to its HTTP(S) base address, without an `/api` suffix. No host is hardcoded in UI components. An invalid mode or missing/invalid real configuration produces an explicit error; it never falls back to mocks. Vite serves frontend assets only.

Enter a backend-issued Bearer token in the real-mode access screen. It remains in page memory only; reloading requires it again. **Never put credentials in `VITE_*` variables, URLs, local storage, or source files.** Changing access clears prior query data and is blocked during pending mutations. The backend enforces access; the frontend does not decode tokens or invent identity.

There is no `/me` endpoint. Employee tokens should open their assigned `/employees/:employeeId` route and can access their own profile/history/recommendations/completion and catalogues. HR tokens can access the directory, all profiles, aggregate analytics, and dataset validation/upload. An employee token is not an HR token; denied access receives an explicit state. The backend must permit the frontend's origin through CORS.

```sh
pnpm typecheck
pnpm lint
pnpm test
pnpm build
pnpm preview
```

`test` runs the full Vitest suite. Target a suite with `pnpm exec vitest run src/services/httpDatasetApi.test.ts`. A production static host must serve `index.html` for application routes so direct links and refreshes work.

## Architecture and pages

React 19, TypeScript, Vite, Tailwind theme tokens, React Router, and TanStack Query provide the existing foundation. No second backend or global state framework is introduced.

| Layer | Responsibility |
| --- | --- |
| `AppShell.tsx`, `ApiAccess.tsx` | Navigation, route focus, responsive sidebar, runtime access |
| `src/pages/` | Employee directory/workspace, HR workspace, dataset workspace |
| `EmployeeProfile`, `CareerTrajectory`, `CareerReadiness`, `SkillGapList` | Profile, career anchors/path, readiness, supplied skill comparisons |
| Recommendation and completion components | First three recommendations, evidence disclosures, impact, operation feedback |
| `src/components/hr/`, `src/components/dataset/` | Aggregate charts and dataset selection/results |
| `src/hooks/` | Query lifecycles and guarded interaction state |
| `src/services/api.ts` | Single adapter-selection point |
| `httpClient.ts`, `httpApi.ts`, `httpMappers.ts`, `httpDatasetApi.ts` | Transport, authentication, contract mapping, snapshot checks |
| `src/types/` | Frontend display models and service interfaces |
| `src/mocks/` | Fixed demo responses and development-only failure scenarios |
| `src/styles.css`, `src/styles/`, `src/i18n/` | Shared visual system and lightweight centralized copy |

Routes: `/` is the employee directory; `/employees/:employeeId` is the employee dashboard; `/hr` is the aggregate dashboard; `/hr/dataset` is dataset management. Unknown routes and employee IDs have recoverable not-found states. Selection and career reads are employee-scoped; failed career reads retain the profile.

## Real API integration

All HTTP calls stay in the service layer. The client unwraps `{ data, meta }`, preserves structured errors, adds the runtime Bearer token, supports abort/timeout, and does not automatically retry mutations. Paginated employee, history, skills, and event reads preserve server order and require consistent snapshot metadata. Career/profile assembly checks dataset versions; bounded retries handle snapshot changes without combining versions.

If the initially loaded profile and career assessment carry different snapshot versions, the dashboard withholds the target and assessment and offers a manual, read-only refresh of both. Failed refreshes keep the mismatched insights hidden; no automatic retry loop or mutation is triggered. Changing API access or refreshing an imported dataset cancels pending manual snapshot reads so late responses cannot overwrite newer state.

| Operation | Contract path |
| --- | --- |
| Employee directory/detail/history | `GET /employees`, `/employees/{id}`, `/employees/{id}/history` |
| Skill names and event catalogue | `GET /skills`, `/events` |
| Career assessment and recommendations | `GET /employees/{id}/recommendations` |
| Aggregate HR analytics | `GET /hr/analytics` |
| Complete activity | `POST /activities/{eventId}/complete` |
| Validate/import dataset | `POST /datasets/validate`, `/datasets/upload`; query parameter `mode=append` or `mode=replace` |

IDs come from `employee_id` and `event_id`; none are substituted for live requests. Profiles use `full_name`, role, grade, department, optional tenure, and supplied career goal. Employee detail's `effective_skills` is authoritative; directory skills are baseline values. Skill names come from the versioned catalogue.

Readiness is **0–1**, displayed as a percentage without a new formula or whole-percent rounding. For example, `0.675` displays as `67.5%`; long values appear below the ring without truncation. Before/after readiness appears only when supplied. The pinned domain contract defines skill levels **0–5**, so the real mapper supplies `scaleMax: 5`; mock/custom display records retain their explicit scales. Current, required, gap, critical status, and actual gain are copied from supplied fields. Bar geometry and hours-to-minutes formatting are presentation only.

The live response supplies a career target but no ordered trajectory path. The UI shows known current/target anchors with a missing-path state; it does not infer intermediate positions, promotions, or a next grade. Mock trajectories demonstrate supplied promotion/transition paths and terminal Lead states. Missing target, readiness, skills, and recommendations remain distinct empty states.

Recommendation order is preserved; the UI displays the first three without sorting or recalculating scores. Simulation maps supplied skill impact and readiness before/after. Factors retain raw, normalized, weight, and contribution fields. Structured facts, evidence paths, scoring evidence, history signals, and simulation evidence remain available when natural-language explanation is absent. Unsupported optional metadata remains unavailable. Returned explanation language/source are retained; employee `kk`, `ru`, or `en` preferences do not automatically translate the English interface.

## Completion and refresh

Completion sends `{ "employee_id": "…" }` and an `Idempotency-Key`. Explicit retry reuses the same key for the employee/activity within the current access session. The adapter verifies that the returned completed activity identifies that employee and event. It does not replace actual completion with the recommendation's projected values.

Synchronous guards prevent duplicate clicks. Acknowledged completion, including an authoritative already-completed response, triggers fresh employee/career reads and cached history when present. Responses are published together after identity/version checks; the matching directory entry is updated. HR analytics are marked stale for the next visit. Selection and route remain stable, including when navigating away during completion.

If refresh fails, acknowledgement remains and **Retry refresh** repeats reads only. It never resubmits completion. Refreshes have a bounded timeout and preserve the prior snapshot on failure. Authentication, unavailable activity, missing employee, duplicate, and transient failures receive distinct handling. Business changes always come from refreshed adapter data.

## HR analytics

The dashboard consumes backend aggregates, preserves supplied row order, and never builds employee rankings. Exact values remain visible beside accessible bars; relative chart widths do not define new metrics. Supplied zero and missing data are distinct.

The real mapper uses `employee_count`, common gaps, `employees_without_next_step` coverage/count/evaluated/pending fields, `participation_summary`, and supplied activity-status counts. Coverage completeness and gap basis remain visible. Status counts represent records, not inferred employee totals. Supported statuses are `completed`, `in_progress`, `no_show`, `dropped`, `declined`, and `overdue`.

The current contract does **not** provide employees-in-development, participation rate, or per-activity participation counts. These remain unavailable in real mode; the frontend does not derive substitutes from participating employees or history. Mock analytics intentionally show a richer fixed aggregate example.

## Dataset workflow and safety

Select JSON/CSV files, assign their roles, select the mode, validate, review the server response, then import. Filename-based role suggestions are editable. Selection checks cover only extensions, unique roles, and required multipart fields; the frontend never parses records or duplicates server schema/reference validation.

- **Append** accepts employees, activity history, or both.
- **Replace** requires employees, activity history, events, and skills. The UI explains replacement and labels the final action **Replace active dataset**.
- Multipart fields are `employees_file`, `activity_history_file`, `events_file`, and `skills_file`. Mode is a query parameter.

Validation maps `valid`, `counts`, `errors`, `mode`, and `version`. Error code, location, message, and order are preserved. Counts map directly, including `role_profiles` and `history`; no record total is calculated. Long issue lists expand in batches. Partial/conflicting responses cannot enable import.

The backend returns **no validation token** and revalidates on upload. The frontend's `validationId` is only a local receipt binding the exact File objects, roles, and mode. It is never transmitted. Editing a selection invalidates it; dispatching an upload consumes it. The server must explicitly return `uploaded: true` before import is acknowledged.

Dataset upload has **no idempotency guarantee**. A lost connection, timeout, server failure, or malformed acknowledgement can mean the import already happened. The UI shows an unknown outcome, locks another import, and offers read-only application refresh. That refresh does not prove import success; an operator must check server state before another submission. A definitive rejection permits correction and revalidation. No automatic upload replay occurs.

After confirmed import, affected employee/history/recommendation/event/HR queries are invalidated and active data refreshed. Failed refresh preserves import acknowledgement and permits reads only. Successful confirmed refresh clears old completion acknowledgements; the adapter also clears cached catalogues and completion keys after confirmed upload. Unrelated UI preferences remain intact.

Within the current browser session, operation guards prevent dataset import during pending completion or its unresolved refresh, and prevent completion during pending/uncertain import or its unresolved refresh. Visible feedback explains the block. These frontend guards do not prevent concurrent changes from other clients; authoritative concurrency and data integrity remain backend responsibilities.

## Isolated mock demo and manual QA

Mock mode makes no backend requests. Fixed fixtures provide three illustrative employees, ordered recommendations, career paths, and explicit before/after completion snapshots. Aigerim's three activities work in any order through a fixed transition table. The UI does not simulate business changes. Reloading resets mock state; route changes preserve in-memory selections and operations.

HR mocks describe a separate illustrative organization and do not recalculate after mock completion. Dataset mocks return preset validation/import results without reading, applying, or saving files. `test-fixtures/dataset/` contains **synthetic picker samples, not backend-compatible business schemas**. `test-fixtures/api/` records the pinned API fixture provenance.

Suggested demo:

1. Open `/employees/demo-aigerim`; show profile, target, readiness, and critical gaps.
2. Expand **Why this recommendation?** and inspect supplied impact/evidence.
3. Complete a development step; show loading, updated skills/readiness, and refreshed recommendations.
4. Switch to Daniyar for a transition, then Madina for the terminal-role state.
5. Open `/hr` for aggregate insights.
6. Open `/hr/dataset`, select `sample-employees.json`, retain the employees role, validate, and import the preset mock response.

Development-only QA scenarios are selected once at reload with `?mockScenario=NAME`; real mode and production builds do not use them.

| Route | Scenario names |
| --- | --- |
| `/` | `empty`, `error`, `retry`, `slow` |
| `/employees/demo-aigerim` | `career-error`, `slow-career`, `missing-trajectory`, `empty-trajectory`, `missing-readiness`, `precision`, `api-precision`, `no-gaps`, `partial-skills`, `skill-scales` |
| Employee recommendations | `recommendations-one`, `recommendations-order`, `recommendations-empty`, `recommendations-partial`, `recommendations-no-explanation`, `recommendations-long` |
| Employee completion | `completion-slow`, `completion-error`, `completion-refresh-error`, `completion-refresh-timeout`, `completion-incomplete`, `completion-partial`, `completion-duplicate`, `completion-unavailable`, `completion-missing-employee` |
| `/hr` | `hr-empty`, `hr-partial`, `hr-zero`, `hr-error`, `hr-retry`, `hr-slow` |
| `/hr/dataset` | `dataset-invalid`, `dataset-long-errors`, `dataset-partial`, `dataset-incomplete`, `dataset-empty`, `dataset-validation-error`, `dataset-import-error`, `dataset-refresh-error`, `dataset-slow` |

`dataset-import-error` verifies the locked unknown-outcome state, not mutation retry. `dataset-refresh-error` verifies read-only retry after acknowledged import. `/employees/unknown-profile` checks not-found handling. Remove the parameter and reload to restore normal fixtures.

## Design, accessibility, and deployment boundary

The shared deep-green/neutral system uses restrained cards, readable charts, responsive grids, and reduced-motion support. Navigation includes a skip link, visible focus, route focus, and keyboard-operated mobile menu. Recommendation disclosures are native keyboard controls; selection, loading, errors, and action feedback are labelled and announced. Values do not depend on color, animation, or hover alone.

UI copy stays in small `src/i18n/` dictionaries for future localization. No translation framework, chatbot, ranking engine, or proprietary branded pages are added. The original Nano Banana image was not available in this workspace; the established written visual direction is preserved.

Real integration is implemented against the pinned contract. Deployment verification still requires an actual backend base URL, valid role-specific tokens, CORS, and an agreed test dataset. Mock browser success and fixture-based contract tests do not demonstrate a successful live mutation. Final command results, browser coverage, exact changed files, and branch verification are recorded separately in the checkpoint report.
