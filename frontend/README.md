# Career Quest frontend

Adilet's frontend application. Checkpoint 7 adds dataset file selection, validation-result presentation, import acknowledgement, and application refresh within the HR area. The employee and aggregate HR dashboards remain available. All source and project configuration live in this directory.

## Run locally

Use Node.js 22.12 or newer and pnpm 11.25.0.

```sh
pnpm install --frozen-lockfile
pnpm dev
```

Open the localhost URL printed by Vite. The default is http://127.0.0.1:5173.

```sh
pnpm typecheck
pnpm lint
pnpm test
pnpm build
pnpm preview
```

The repository contains no server application for this frontend. Vite serves frontend assets only.

## Routes

- `/`: sample employee directory, loaded through the API adapter.
- `/employees/:employeeId`: employee dashboard with profile, target, readiness, trajectory preview, skill comparisons, and up to three recommendations.
- `/hr`: aggregate HR dashboard with overview metrics, common skill gaps, next-step coverage, activity participation, and status distribution.
- `/hr/dataset`: dataset management, accessible through **Manage dataset** in the HR header. Uses the same shell and HR navigation.
- Other paths: not-found view.

The employee selector works across routes. Unknown employee IDs show a recoverable not-found state. Browser back/forward and direct route reloads work on the Vite server. A production static host must route unknown application paths to `index.html`.

The dashboard displays supplied values and preserves recommendation ordering. Profile and career queries use separate employee-scoped cache keys; changing employees never shows the previous employee's assessment. A career query failure leaves the profile visible and provides a retry. Recommendation loading and errors use this same centralized query lifecycle.

## API and mock data

`src/types/api.ts` defines the frontend-facing interface. `src/types/domain.ts` defines display models, not a finalized backend transport schema. Components consume hooks and the service facade; they never import fixtures.

`src/services/api.ts` is the only adapter-selection point. Mode defaults to `mock`. Copy `.env.example` to `.env.local` to set an explicit mode. `VITE_API_BASE_URL` is reserved for the later HTTP adapter. Never place secrets in Vite environment variables.

Real mode currently returns a configuration error. It never silently falls back to demo records. There are no assumed live endpoints and no HTTP adapter until Bekarys's contracts are available.

The mock adapter returns cloned, static synthetic fixtures with asynchronous loading and abort support. Fixed response examples include promotion, same-grade career transition, and a Lead without a next target. It contains no recommendation, scoring, gap, or readiness calculations. Tests cover failures, empty results, cancellation and response isolation.

The mock adapter implements activity completion with fixed response snapshots and dataset validation/import with preset responses. Real mode remains explicitly unconfigured for every operation; no HTTP endpoint or live mutation contract has been invented.

## Integration ownership

- Bekarys: HTTP paths, transport schema, identity, errors, auth/CORS, completion semantics, dataset validation/import and HR aggregates.
- Zhanibek: career targets, trajectory, gaps, readiness, recommendation order/scores, projected impact and explanations.
- Adilet: presentation, API adapters, navigation, query lifecycle and interaction states.

Readiness view models use a 0–1 value; this is provisional and must be normalized by the future adapter after the backend unit is confirmed. The meter exposes the original value and 0–1 range; its visible percentage retains fractional precision (for example, 0.675 becomes 67.5%, not 68%). Extremely small values use scientific percentage notation to remain readable. This is number formatting only; no readiness score is calculated, rounded to a whole percent, or clamped. JSON numeric precision is bounded by JavaScript's number type.

Skill scales come from each record's optional `scaleMax` and are explicitly displayed. Gap numbers and critical flags are used exactly as supplied. A missing scale leaves the numbers visible and the comparison unavailable; no default scale is assumed. Out-of-scale levels remain visible without being clamped. Percentage formatting and comparison-bar geometry are presentation only. No UI may infer a missing score, target, gap or recommendation.

The readiness card can show an activity projection from the first recommendation in API-provided order, with the activity title as context. Both `readinessBefore` and `readinessAfter` must be supplied as valid 0–1 values; otherwise the projection is omitted. These values are formatted independently of the current assessment, with no calculated uplift, substitute score, re-ranking, or activity-completion behavior. Projections remain explicitly labelled as projected values. The existing Aigerim fixture supplies this pair; no additional demo scores are invented.

Optional employee `tenureLabel` and `careerGoal` strings are displayed when supplied; the frontend does not infer them from role, grade, or dates. Target `null` means no target. Failed target requests remain distinct from that empty state. Recommendation scores are not shown in this preview.

Trajectory `positions` are rendered in the supplied order with their supplied `past`, `current`, `intermediate`, `target`, or `future` states. The adapter owns these labels and must align them with the profile/target. The frontend does not sort grades, infer intermediate roles, or mark milestones from readiness. When a path omits current/target anchors, the known profile and target are shown separately without inserting nodes into the path. Null/empty trajectories have an explicit unavailable state. Lead roles use the same data-driven behavior; no special promotion rule is applied.

## Dashboard verification

Default mock profiles cover a promotion with past/current/target/future positions, a same-grade career transition with an intermediate position, and a Lead without target/readiness/gaps/recommendations. Aigerim has three supplied recommendations; Daniyar and Madina have none.

For manual QA, append these development-only query parameters to a URL and reload. Scenario selection is read once by the API adapter; it never adds error simulation to UI components and is ignored in production builds.

- `/?mockScenario=empty`: empty employee directory and selector.
- `/?mockScenario=error`: persistent API failures.
- `/?mockScenario=retry`: first directory request fails, then succeeds when retried.
- `/employees/demo-aigerim?mockScenario=career-error`: career request fails once while profile stays visible; Try again recovers it.
- `/employees/demo-aigerim?mockScenario=slow`: slow profile/directory responses for loading checks.
- `/employees/demo-aigerim?mockScenario=slow-career`: slow assessment for switching/cancellation checks.
- `/employees/unknown-profile`: employee not found.

Checkpoint 3 assessment scenarios (append to an employee route and reload):

- `?mockScenario=missing-trajectory`: current/target facts remain, but no path is fabricated.
- `?mockScenario=empty-trajectory`: an empty supplied positions list.
- `?mockScenario=missing-readiness`: no percentage is invented; other sections remain available.
- `?mockScenario=precision`: supplied readiness 0.675 displays as 67.5%.
- `?mockScenario=no-gaps`: explicit empty skill-gap state.
- `?mockScenario=skill-scales`: fixed records with scales 100, 10, and an absent scale.

Checkpoint 4 recommendation scenarios (append to an employee route and reload):

- `?mockScenario=recommendations-one`: one existing recommendation.
- `?mockScenario=recommendations-order`: supplied order deliberately differs from score order.
- `?mockScenario=recommendations-empty`: no recommendations.
- `?mockScenario=recommendations-partial`: minimal and partially populated records, including zero values and missing readiness-after/skill-after.
- `?mockScenario=recommendations-no-explanation`: structured evidence remains available without explanation text or factors.
- `?mockScenario=recommendations-long`: a long, multi-paragraph synthetic explanation for responsive QA.

Return to a URL without the scenario parameter and reload to restore normal mocks. Adapter tests cover response isolation, failures and cancellation. Presentation tests cover zero/missing readiness, API-supplied gaps and scales, recommendation order/limit, transition and Lead states, optional tenure, and distinct missing/error target states.

## Recommendation presentation and integration

`RecommendationList` shows the first three records in supplied order. It never sorts, filters, ranks, or recomputes scores. The first card is visually emphasized by its position alone, with no numeric ranking badge. `RecommendationCard` exposes activity metadata, skill levels and readiness projections. `RecommendationExplanation` uses a native, keyboard-accessible disclosure that starts closed and preserves all supplied explanation text. Expansion resets when the employee changes. Reduced-motion preferences disable expansion animation.

`ActivityImpact` displays the supplied current, after, required, and critical fields. The optional `gain` field is provisional because the previous frontend model had no activity-gain field; the real adapter must map an explicitly supplied backend field before using it. Missing gain is omitted and never computed as after minus current. Missing skill levels display “Not provided”, and a missing critical flag is not interpreted as false. Skill-impact scales are not part of the current contract, so these comparisons use labelled values rather than invented progress-bar scales.

`ReadinessImpact` shares the formatter and range validation used by `CareerReadiness`. Each provided before/after value is shown independently, including zero; the missing side remains “Not provided”. No uplift or substitute assessment is calculated. The existing top-level readiness projection still requires both values.

Factor labels, values, and ordering are preserved. Their units and scale have not been agreed, so they are displayed as supplied numbers, not percentages or normalized bars. Recommendation scores remain hidden. The entire explanation object, its text/factors, skill-impact array, readiness-impact values, career-impact label, activity type, and duration are optional in the display model. Identity and title remain required. Missing explanation text does not hide structured evidence. No explanation is generated by the frontend.

Cards accept `onStart?: (recommendation: Recommendation) => void`, passed through the list. The workspace connects this callback to `useActivityCompletion`. The CTA is labelled “Complete development step” to describe the operation accurately. Standalone cards without a handler stay disabled. No API calls or business updates occur inside cards.

## Activity completion and refresh

The existing service contract is `completeActivity(employeeId, eventId): Promise<void>`: a fulfilled call acknowledges completion, with no response body required. The hook then refetches the employee and career overview through the same adapter. History is refetched if it already has a query-cache entry. The returned employee also replaces its matching directory entry. No new skills, readiness, gaps, scores, recommendation order, or activity effects are calculated by the UI.

`refreshEmployeeState` cancels older reads, waits for all required responses, checks required identity/array fields, and then publishes the returned snapshot. On refresh failure it keeps the previous snapshot, preserves the completion acknowledgement, and offers **Retry refresh**. This retries reads only. Refresh requests time out after 10 seconds and are aborted; late results cannot update the cache. Optional recommendation fields retain their normal missing-data presentation.

Operation state lives under an employee-specific query key. A synchronous guard prevents duplicate submissions, even before React updates the disabled buttons. Changing the selected employee does not cancel an already submitted completion, navigate the app, or apply results to the wrong employee. Returning to the original employee shows their result and acknowledgement. Completed event IDs are retained for the current app session so stale cards cannot submit the same event again.

`ALREADY_COMPLETED` is treated as an acknowledgement followed by reads, not another mutation. `RECOMMENDATION_UNAVAILABLE` offers a refresh without claiming completion. `NOT_FOUND` asks the user to choose another employee. Transient completion errors support an explicit retry; completion is never retried automatically. The future real adapter must define idempotency for the employee/event pair and map authoritative conflict/error responses before enabling live completion. Authentication, endpoint shape, response payloads, and consistency guarantees still require Bekarys's contract.

`completionFixtures.ts` contains eight fixed states and a transition table for Aigerim's three activities in any order. Example supplied snapshots change System Design from 2 to 3 and readiness from 0.67 to 0.79 after the workshop; these are fixed synthetic adapter responses, not formulas. Remaining recommendations and their projections are explicitly listed for each state. The adapter records history once and rejects duplicates. No state is persisted to a server or local storage: a full browser reload resets the mock demo, while route/employee changes preserve it. Other employees have no recommended activities in the normal demo.

The feedback panel announces submission, acknowledgement, refresh, success, or failure. Buttons are disabled during submission/refresh, keyboard focus moves to feedback when a clicked card disappears, and returned progress values use restrained animation with reduced-motion support. The success comparison shows the previous assessment and the newly fetched value labelled “Now”; it does not use the recommendation's projected value as the actual result.

Checkpoint 5 QA scenarios (append to `/employees/demo-aigerim` and reload):

- `?mockScenario=completion-slow`: visible submission and refresh phases.
- `?mockScenario=completion-error`: first completion fails; manual retry succeeds.
- `?mockScenario=completion-refresh-error`: completion succeeds but the first refresh fails.
- `?mockScenario=completion-refresh-timeout`: the first refresh exceeds the 10-second timeout; retry recovers.
- `?mockScenario=completion-incomplete`: first refresh returns an adapter validation error.
- `?mockScenario=completion-partial`: refreshed recommendations omit optional fields.
- `?mockScenario=completion-duplicate`: adapter reports already completed and returns the after-state.
- `?mockScenario=completion-unavailable`: an activity is no longer available; refresh replaces the stale list.
- `?mockScenario=completion-missing-employee`: the employee becomes unavailable at submission.

Interaction tests use jsdom and Testing Library to exercise the actual dashboard, API callbacks, loading/disabled states, duplicate protection, refresh/retry behavior, optional data, and employee selection. The mock and refresh services also have direct isolation, conflict, snapshot-integrity, and timeout tests.

## HR analytics

`useHRAnalytics` reads only `api.getHRAnalytics({ signal })` using the existing organization-level query key. Employee selection does not scope these analytics to an individual. No employee histories, recommendations, or skill records are fetched to construct HR metrics. The page preserves the supplied row order, exposes exact counts as text, and supports direct navigation, loading, manual refresh, retry, empty responses, partial metrics, and missing row counts. Failed refreshes retain the last successful response with a visible warning.

The existing `HRAnalytics` view model retains `withoutNextStep` and `activityStatuses`. All fields may be omitted or null; these mean unavailable. Supplied zero remains zero. Missing lists have section-specific empty states; no missing status category is fabricated. Negative/non-finite counts and out-of-range rates are unavailable rather than silently clamped. The optional `activityParticipation` array (`activityId`, `title`, `participantCount`) is provisional until Bekarys confirms the transport contract. The real adapter must validate and map its response into this model, including supported status enums.

`participationRate` uses a provisional 0–1 representation and is formatted only for display (0.675 → 67.5%). Its denominator, reporting period, scope, definitions of “in development” and “without next step”, and the meaning of status counts must be supplied/confirmed by the backend. Status counts are labelled records, not employees. There are no inferred dates, trends, totals, percentages by category, coverage ratios, or alternative business metrics. The backend remains responsible for access control when live HR data is connected.

Accessible HTML/CSS horizontal bars suit these compact datasets without adding a chart dependency. The only chart arithmetic sets relative bar widths against each chart's largest supplied count; it does not change counts or their order, derive a business metric, or normalize them against employee totals. The rate meter retains the supplied 0–1 value. Text labels expose every value without relying on color or hover. Charts have independent scales and row counts may overlap. Responsive grids, wrapping labels, and reduced-motion support use the existing visual system.

`src/mocks/hrFixtures.ts` holds fixed, synthetic organizational analytics for an illustrative 24-person organization, independent of the three sample employee profiles. This replaces the initial HR placeholder fixture. These analytics are not calculated from local employee history or updated by the mock completion flow. The UI labels them as fixed sample analytics. Live mode remains explicitly unconfigured, and no backend endpoint or analytics engine has been created.

Checkpoint 6 QA scenarios (append to `/hr` and reload):

- `?mockScenario=hr-empty`: no analytics supplied.
- `?mockScenario=hr-partial`: supplied counts, missing metrics/row count, and empty sections.
- `?mockScenario=hr-zero`: explicit zero metrics and zero completed records.
- `?mockScenario=hr-error`: persistent HR-only request failure.
- `?mockScenario=hr-retry`: first HR request fails; Try again recovers.
- `?mockScenario=hr-slow`: delayed HR request to verify loading.

HR integration tests cover direct routing/navigation, supplied values and precision, unsorted row order, all six statuses, missing versus zero, loading, error/retry, retained data after failed refresh, aggregate-only privacy, and return to the employee flow. Adapter tests cover response isolation, unchanged fixed analytics after employee completion, cancellation, partial fields, and explicit real-mode failure.

## Dataset selection, validation, and import

`DatasetUpload` uses `useDatasetUpload`, which calls the existing `validateDataset(files: File[]): Promise<DatasetValidationResult>` and `uploadDataset(files: File[], validationId: string): Promise<void>` operations. No fetch calls, file parsing, CSV/JSON schema checks, reference checks, or business validation live in components. The original browser File objects are sent unchanged to the adapter. The current mock contract supports `.json` and `.csv`; `services/datasetConfig.ts` centralizes the picker hint and extension-only selection check. MIME types can be absent or vary by platform and are not treated as authoritative. File-size/count limits and business schemas await the real contract.

The picker is keyboard accessible and supports multiple files; dropping/reselecting replaces the batch. The list shows names and presentation-formatted byte sizes. Unsupported extensions stay visible with a removal action and block validation. Removing, clearing, or reselecting files immediately discards the previous validation response and import authorization. Browser file contents are never read. Cancelling the picker preserves the current selection.

Import requires an explicit `valid: true`, a nonempty `validationId`, and no returned errors. Empty, null, missing-token, and contradictory responses never enable import. Optional summary counts (`employees`, `skills`, `events`, `activityHistory`, `recordsProcessed`), warnings, and issue `record` fields extend the existing view model provisionally. The adapter must map its transport response into this shape. Only supplied summary fields appear; zero remains zero, explicit missing/invalid values say **No data available**. Optional omitted summaries are safe. Error/warning details preserve supplied file, row, record, field, message, and ordering. Lists initially show 10 issues and expand by 10, without truncating messages.

Synchronous operation-state updates prevent duplicate validation/import clicks. Files cannot change during requests or after import acknowledgement. Selection, validation, and acknowledgement live in the query cache for this browser session, so navigating away and back does not lose an in-flight operation or resubmit it. **Select another dataset** releases the previous selection after a successful refresh. Nothing is persisted to local storage, and reloading clears the selection. Request failures require explicit retry; import is never retried automatically.

A resolved `uploadDataset` acknowledges import without requiring a response body. `refreshDatasetState` then cancels older reads and invalidates only employees, employee details, recommendations, history, events, and HR analytics. It refetches the directory and HR analytics, and refreshes other active affected queries; inactive resources remain stale for their next visit. Unrelated query state and local completion acknowledgements are preserved. This refresh stays on the dataset page, has a 10-second timeout, and never computes analytics. A refresh failure keeps import acknowledged and offers **Retry refresh**, which only repeats reads. It cannot repeat the import. Live import replacement/merge semantics and the handling of concurrent employee operations still need the backend contract before real mode can be enabled.

Mock validation always returns a predetermined fixture independent of file content. Import checks only the issued token and unchanged File references, then acknowledges; it does not parse or store the selected dataset, alter the demo profiles, or recalculate HR analytics. Issued mock tokens are scoped to one batch and successful acknowledgement is idempotent for that token. The UI explicitly identifies this behavior. `test-fixtures/dataset/` contains synthetic browser file-selection samples, **not** a proposed backend schema or jury-ready business dataset.

Live integration is pending Bekarys's endpoint paths, multipart/file-role conventions, supported formats/limits, authoritative validation response, opaque token lifetime/binding, warning semantics, authentication, and import consistency/idempotency rules. The real backend should make retries with the same validation token safe when a prior response is lost. No real import is enabled until those guarantees are mapped through the centralized adapter. Frontend validation does not replace backend checks.

Checkpoint 7 QA scenarios (append to `/hr/dataset` and reload):

- Default mock: validation and import succeed with a supplied summary and warning.
- `?mockScenario=dataset-invalid`: fixed validation errors; import stays unavailable.
- `?mockScenario=dataset-long-errors`: 35 supplied sample errors with long metadata/messages.
- `?mockScenario=dataset-partial`: supplied zero employees and unavailable skills; optional metrics omitted.
- `?mockScenario=dataset-incomplete`: missing validation token, so import stays unavailable.
- `?mockScenario=dataset-empty`: empty validation response.
- `?mockScenario=dataset-validation-error`: first validation request fails; manual retry succeeds.
- `?mockScenario=dataset-import-error`: first import request fails; manual retry succeeds.
- `?mockScenario=dataset-refresh-error`: import succeeds, first refresh fails; retry refresh does not reimport.
- `?mockScenario=dataset-slow`: three-second validation/import requests for loading and duplicate-submission checks.

Interaction tests cover selection/drop/removal, unsupported formats, loading, token invalidation on file changes, backend issue display/pagination, partial/empty responses, import retries, no duplicate requests, refresh scope, and navigation during import. Adapter tests verify preset responses, token/batch binding, idempotent acknowledgement, response isolation, and explicit live-mode failure. Refresh tests cover active resources and timeout behavior.

## Visual foundation

`src/styles.css` contains Tailwind theme tokens and shared shell/component styles. The written specification informs the green/neutral palette, generous desktop spacing and restrained cards. The Nano Banana image has not been supplied, so visual-reference matching remains pending. No proprietary branded pages or assets are copied.

UI text is centralized in `src/i18n/en.ts`. English is the current UI language; employee language preferences do not yet translate the interface. Navigation supports keyboard use, focus indicators, a skip link, route-change focus, loading announcements and reduced motion.

## Next checkpoint

Checkpoint 7 is complete. Stop before Checkpoint 8 until the user's next instruction. Before making changes, verify that the branch is exactly `feat/adilet` and that all edits stay under `frontend/`.
