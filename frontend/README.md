# Career Quest frontend

Adilet's frontend application. Checkpoint 1 provides the application shell, routes, design tokens, and a typed mock API boundary. All source and project configuration live in this directory.

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

## Checkpoint 1 routes

- `/`: sample employee directory, loaded through the API adapter.
- `/employees/:employeeId`: selected employee identity and workspace preview.
- `/hr`: HR workspace placeholder; charts arrive in Checkpoint 6.
- Other paths: not-found view.

The employee selector works across routes. Unknown employee IDs show a recoverable not-found state. Browser back/forward and direct route reloads work on the Vite server. A production static host must route unknown application paths to `index.html`.

The detailed employee dashboard, trajectory, readiness, recommendation cards and activity completion interaction are deliberately deferred to their approved checkpoints. No inactive action buttons claim those features work.

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

Readiness view models use a 0–1 value; this is provisional and must be normalized by the future adapter after the backend unit is confirmed. No UI may infer a missing score, target, gap or recommendation.

## Visual foundation

`src/styles.css` contains Tailwind theme tokens and shared shell/component styles. The written specification informs the green/neutral palette, generous desktop spacing and restrained cards. The Nano Banana image has not been supplied, so visual-reference matching remains pending. No proprietary branded pages or assets are copied.

UI text is centralized in `src/i18n/en.ts`. English is the current UI language; employee language preferences do not yet translate the interface. Navigation supports keyboard use, focus indicators, a skip link, route-change focus, loading announcements and reduced motion.

## Next checkpoint

Checkpoint 2 will replace the employee workspace preview with the dashboard. Do not start it without the user's next instruction. Before making changes, verify that the branch is exactly `feat/adilet` and that all edits stay under `frontend/`.
