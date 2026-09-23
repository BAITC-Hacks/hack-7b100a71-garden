# Career Quest frontend

Adilet's frontend application. Checkpoint 3 extends the employee dashboard with complete supplied trajectories, precise readiness presentation, and explicit skill scales. All source and project configuration live in this directory.

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
- `/hr`: HR workspace placeholder; charts arrive in Checkpoint 6.
- Other paths: not-found view.

The employee selector works across routes. Unknown employee IDs show a recoverable not-found state. Browser back/forward and direct route reloads work on the Vite server. A production static host must route unknown application paths to `index.html`.

The dashboard displays supplied values and preserves recommendation ordering. Profile and career queries use separate employee-scoped cache keys; changing employees never shows the previous employee's assessment. A career query failure leaves the profile visible and provides a retry. Expanded explainability and activity completion remain for later checkpoints.

## API and mock data

`src/types/api.ts` defines the frontend-facing interface. `src/types/domain.ts` defines display models, not a finalized backend transport schema. Components consume hooks and the service facade; they never import fixtures.

`src/services/api.ts` is the only adapter-selection point. Mode defaults to `mock`. Copy `.env.example` to `.env.local` to set an explicit mode. `VITE_API_BASE_URL` is reserved for the later HTTP adapter. Never place secrets in Vite environment variables.

Real mode currently returns a configuration error. It never silently falls back to demo records. There are no assumed live endpoints and no HTTP adapter until Bekarys's contracts are available.

The mock adapter returns cloned, static synthetic fixtures with asynchronous loading and abort support. Fixed response examples include promotion, same-grade career transition, and a Lead without a next target. It contains no recommendation, scoring, gap, or readiness calculations. Tests cover failures, empty results, cancellation and response isolation.

Mutation signatures are reserved in the interface. Completion and dataset mutations currently reject with `UNAVAILABLE`; no fake successful mutation is exposed. The scripted before/after completion scenario belongs to Checkpoint 5.

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

Default mock profiles cover a promotion with past/current/target/future positions, a same-grade career transition with an intermediate position, and a Lead without target/readiness/gaps/recommendations. The existing recommendation previews are unchanged.

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

Return to a URL without the scenario parameter and reload to restore normal mocks. Adapter tests cover response isolation, failures and cancellation. Presentation tests cover zero/missing readiness, API-supplied gaps and scales, recommendation order/limit, transition and Lead states, optional tenure, and distinct missing/error target states.

## Visual foundation

`src/styles.css` contains Tailwind theme tokens and shared shell/component styles. The written specification informs the green/neutral palette, generous desktop spacing and restrained cards. The Nano Banana image has not been supplied, so visual-reference matching remains pending. No proprietary branded pages or assets are copied.

UI text is centralized in `src/i18n/en.ts`. English is the current UI language; employee language preferences do not yet translate the interface. Navigation supports keyboard use, focus indicators, a skip link, route-change focus, loading announcements and reduced motion.

## Next checkpoint

Checkpoint 3 is complete. Stop before Checkpoint 4 until the user's next instruction. Before making changes, verify that the branch is exactly `feat/adilet` and that all edits stay under `frontend/`.
