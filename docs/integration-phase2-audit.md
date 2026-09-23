# Integration Phase 2 — frontend + реальный API

## Итог и границы

Phase 2 выполнена только в worktree `codex/team-integration`. Backend,
recommendation engine, AI, eligibility, scoring, chronology, зависимости Python
и тесты Phase 1 не менялись. Все **425** тестов Phase 1 сохранены; frontend —
**120 passed**. Ветки `main`, `zhanibek`, `feat-beka`, `feat/adilet` не изменялись.
Phase 2 закоммичена локально; push и merge в main не выполнялись.

Baseline: `3a90322a728f592888929903cb4a9f671d048b3e`.
Перед объединением выполнен fetch `origin/feat/adilet` и сверка с `git ls-remote`.
Последний интегрированный commit Adilet:
`002e78b0485c509a4fc6619f2e5ef7c0cbb05f5a` —
`feat(frontend): add employee dashboard career and skills`.
По сравнению с `b300e7d` добавлен один commit: 23 файла, +939/−79;
развиты profile, career, skills и тесты, HTTP ещё оставался placeholder.
Merge: `4d4bcd89e8d7b793a1da3685cad9e9932ab36442`; конфликтов не было.
Сразу после merge, до интеграционных правок frontend: **425 passed**.

## Архитектура и авторизация

`types/transport.ts` → `services/httpApi.ts` → `types/domain.ts` → hooks → UI.
Backend JSON не менялся. Адаптер сохраняет rank, score, explanation, raw evidence,
статус и snapshot version; переименовывает display-поля и переводит часы в минуты.
Real mode включён по умолчанию; mock выбирается только явно. Нет скрытого fallback
на fixtures при ошибках backend.

Base URL: публичная настройка `VITE_API_BASE_URL`, default `http://127.0.0.1:8000`.
Адаптер передаёт Bearer, разбирает envelopes/errors, проходит все страницы,
проверяет версии, отменяет устаревшие чтения. Версии между параллельно полученными
каталогами и данными должны совпадать. Ошибки сохраняют HTTP status, backend code
и details. Гонки при смене identity/отмене во время чтения JSON покрыты тестами.

Нет выдуманного login/me endpoint или декодирования opaque token. Вход принимает
назначенные роль, employee ID и токен; backend независимо проверяет права.
Employee открывает свой workspace, не запрашивает HR directory, не видит selector
или HR route. HR имеет directory, profile review, аналитику и импорт. Выбор HR
в форме не расширяет серверные права. Токен хранится только в памяти вкладки;
смена identity отменяет запросы и очищает cache.

## Реализованные сценарии

- Employee: профиль, department, role/grade, tenure/work format, language, career
  goal, effective skills; assessment baseline хранится отдельно.
- Career + Skills: только current и target, требования цели, satisfied requirements,
  gaps и critical markers. Readiness берётся из backend и форматируется, не считается
  в React; это покрытие требований, не гарантия повышения.
- Recommendations: Top 1–3 в серверном порядке, реальные type/format/duration,
  target skill impact, projection, explanation kk/ru/en, factors и полный raw JSON.
  `no_next_grade`, `target_satisfied`, `no_eligible_recommendations` — нормальные
  состояния. Приблизительная реконструкция и предупреждения остаются видимыми.
- Completion: один idempotency key и один body на действие и его retry; защита от
  повторного клика, receipt, actual timestamp/logical day, no optimistic gains.
  При нескольких активных назначениях UI требует выбрать record_id.
  После success обновляются profile, history, recommendations и HR. Несовпадение
  snapshot либо ошибка refresh показываются явно; completion временно недоступен.
- HR: только настоящие агрегаты, `gap_basis` текущей роли/грейда, status totals,
  добровольное/обязательное участие, partial/null coverage. Без рейтинга сотрудников.
- Dataset: четыре поля multipart, append/replace, validation → counts → upload,
  backend error details, новый version, invalidation. Для replace обязательны
  все четыре файла. Нет устаревшего validationId.

## Автоматические проверки

| Проверка | Результат |
|---|---|
| Recommendation + AI | 280 passed, 5.14 s |
| Backend | 102 passed, 0.90 s |
| Backend/engine integration | 43 passed, 4.85 s |
| Полный совместный backend run | **425 passed**, 10.63 s |
| Frontend Vitest | **120 passed**, 10 файлов, 2.07 s |
| Frontend production build | Passed; Vite 7.3.6 |
| TypeScript | Passed |
| ESLint | Passed, max-warnings 0 |
| Frozen-lockfile install | Passed |

Выполненные команды из корня (frontend-команды — из `frontend/`):

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/recommendation
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_*.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/integration
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
pnpm test
pnpm build
pnpm exec tsc -b --pretty false
pnpm lint
pnpm install --frozen-lockfile
```

Среда проверки: Python 3.13, Node 24.11.1, установленный pnpm 11.19.0;
project packageManager остаётся 11.25.0. Единственное предупреждение Python —
существующий Starlette TestClient / AnyIO BlockingPortal deprecation.
Frontend тесты разделяют transport mapping, компоненты и query/mutation lifecycle;
они не выдаются за настоящие browser E2E.

## Настоящая браузерная проверка

Выполнена в Codex in-app browser через работающие Vite и Uvicorn.
Backend authorization включена; использовано отдельное временное persisted
хранилище, реальные provider/engine и deterministic missing-key fallback.
OpenAI сеть не вызывалась. Токены не включены в файлы/артефакты.

| Профиль | Реально проверенный результат в UI |
|---|---|
| E0001 | Backend Engineer / Middle, KK explanation; EV_005 rank 1; readiness 58.97% → 66.67%; API Design 2 → 3, System Design 1 → 2; EV_005 исчез, остался EV_036 |
| E0004 | Product Manager / Middle, RU explanation, EV_026 и `target_role`; readiness 42.11% → 52.63%; после completion EV_021, EV_027 |
| E0006 | `no_next_grade`, обычное пустое состояние, без выдуманной цели |
| E0018 | `no_eligible_recommendations`, EN explanation, обычное пустое состояние |
| Новый импортированный ID | Append через validate/upload; version 4, 201 сотрудник; HR открыл новый профиль и реальные рекомендации EV_005, EV_040, EV_036 |
| Replace | Четыре файла выбраны через UI; validation затем upload; version 5, 200 сотрудников, 2743 history records |

HR проверен после двух completion: 2745 записей истории, partial coverage и реальные
агрегаты. После импорта coverage корректно сброшен для новой версии, не показан
как фиктивный ноль. Ошибок browser console не обнаружено. Отдельный тестовый
runtime и серверы остановлены; временный upload fixture удалён. Source dataset
не менялся даже при replace: изменялось только отдельное runtime-хранилище.

[Машиночитаемые результаты](integration-phase2-results.json) отдельно обозначают
наблюдения UI и последующие HTTP readbacks того же backend. Readbacks сохранены
после append (version 4), до тестового replace (version 5). Это не повтор
Phase 1 TestClient-сценария под видом браузерной проверки.

## Сохранность и оставшиеся ограничения

Все семь SHA-256 официального датасета совпадают с Phase 1 и `origin/main`;
значения сохранены в results JSON. `docs/FRONTEND_API_CONTRACT.md` не менялся.
Не добавлены реальные .env, секреты, runtime state, cache, node_modules или dist.
Отслеживаются только публичные `.env.example`. Из backend-ориентированной
документации в корневом README исправлено устаревшее утверждение о неподключённом
движке и добавлена ссылка на frontend.

Блокеров для локального hackathon demo не обнаружено. Ограничения:

- интерфейс преимущественно английский; объяснения берутся из backend на kk/ru/en;
- вход для хакатона с заранее настроенными токенами, без SSO и /me; после reload
  требуется повторный ввод; idempotency actions также живут в памяти вкладки;
- новый профиль доступен HR сразу, employee-token mapping для него настраивается
  на backend отдельно;
- live OpenAI вызов не проверялся; детерминированный fallback проверен;
- проведена одна browser/runtime проверка в IAB, не cross-browser матрица;
- полнота HR recommendation coverage зависит от вычисленных результатов текущей
  версии; UI показывает это ограничение;
- backend остаётся однопроцессным согласно Phase 1.

Распределение ответственности сохранено: Bekarys — API/data/runtime, Zhanibek —
engine/scoring/explanations/integration, Adilet — React presentation. Backend
application models и frontend компоненты не дублировались.

## Точный список файлов

Ниже перечислены все изменения Phase 2 относительно baseline `3a90322`, включая
43 frontend-файла, принятых merge из ветки Adilet. A — новый файл, M — изменённый.

- `M` [README.md](../README.md)
- `A` [docs/integration-phase2-audit.md](../docs/integration-phase2-audit.md)
- `A` [docs/integration-phase2-results.json](../docs/integration-phase2-results.json)
- `A` [frontend/.env.example](../frontend/.env.example)
- `A` [frontend/.gitignore](../frontend/.gitignore)
- `A` [frontend/README.md](../frontend/README.md)
- `A` [frontend/eslint.config.js](../frontend/eslint.config.js)
- `A` [frontend/index.html](../frontend/index.html)
- `A` [frontend/package.json](../frontend/package.json)
- `A` [frontend/pnpm-lock.yaml](../frontend/pnpm-lock.yaml)
- `A` [frontend/pnpm-workspace.yaml](../frontend/pnpm-workspace.yaml)
- `A` [frontend/src/App.tsx](../frontend/src/App.tsx)
- `A` [frontend/src/auth.test.tsx](../frontend/src/auth.test.tsx)
- `A` [frontend/src/components/ActivityHistory.tsx](../frontend/src/components/ActivityHistory.tsx)
- `A` [frontend/src/components/AppShell.tsx](../frontend/src/components/AppShell.tsx)
- `A` [frontend/src/components/CareerReadiness.tsx](../frontend/src/components/CareerReadiness.tsx)
- `A` [frontend/src/components/CareerTrajectory.tsx](../frontend/src/components/CareerTrajectory.tsx)
- `A` [frontend/src/components/CompletionResult.tsx](../frontend/src/components/CompletionResult.tsx)
- `A` [frontend/src/components/DatasetUpload.test.tsx](../frontend/src/components/DatasetUpload.test.tsx)
- `A` [frontend/src/components/DatasetUpload.tsx](../frontend/src/components/DatasetUpload.tsx)
- `A` [frontend/src/components/EmployeeProfile.tsx](../frontend/src/components/EmployeeProfile.tsx)
- `A` [frontend/src/components/EmployeeSelector.tsx](../frontend/src/components/EmployeeSelector.tsx)
- `A` [frontend/src/components/HRAnalyticsPanel.tsx](../frontend/src/components/HRAnalyticsPanel.tsx)
- `A` [frontend/src/components/Icon.tsx](../frontend/src/components/Icon.tsx)
- `A` [frontend/src/components/RecommendationCard.tsx](../frontend/src/components/RecommendationCard.tsx)
- `A` [frontend/src/components/RecommendationList.tsx](../frontend/src/components/RecommendationList.tsx)
- `A` [frontend/src/components/SkillGapList.tsx](../frontend/src/components/SkillGapList.tsx)
- `A` [frontend/src/components/UI.tsx](../frontend/src/components/UI.tsx)
- `A` [frontend/src/components/dashboard.test.tsx](../frontend/src/components/dashboard.test.tsx)
- `A` [frontend/src/components/employeeIntegration.test.tsx](../frontend/src/components/employeeIntegration.test.tsx)
- `A` [frontend/src/components/hr.test.tsx](../frontend/src/components/hr.test.tsx)
- `A` [frontend/src/hooks/useEmployeeDashboard.ts](../frontend/src/hooks/useEmployeeDashboard.ts)
- `A` [frontend/src/hooks/useEmployees.ts](../frontend/src/hooks/useEmployees.ts)
- `A` [frontend/src/hooks/useSession.ts](../frontend/src/hooks/useSession.ts)
- `A` [frontend/src/i18n/en.ts](../frontend/src/i18n/en.ts)
- `A` [frontend/src/main.tsx](../frontend/src/main.tsx)
- `A` [frontend/src/mocks/fixtures.ts](../frontend/src/mocks/fixtures.ts)
- `A` [frontend/src/mocks/mockApi.test.ts](../frontend/src/mocks/mockApi.test.ts)
- `A` [frontend/src/mocks/mockApi.ts](../frontend/src/mocks/mockApi.ts)
- `A` [frontend/src/mocks/scenarios.ts](../frontend/src/mocks/scenarios.ts)
- `A` [frontend/src/pages/EmployeeDirectory.tsx](../frontend/src/pages/EmployeeDirectory.tsx)
- `A` [frontend/src/pages/EmployeeWorkspace.test.tsx](../frontend/src/pages/EmployeeWorkspace.test.tsx)
- `A` [frontend/src/pages/EmployeeWorkspace.tsx](../frontend/src/pages/EmployeeWorkspace.tsx)
- `A` [frontend/src/pages/HRWorkspace.tsx](../frontend/src/pages/HRWorkspace.tsx)
- `A` [frontend/src/pages/NotFound.tsx](../frontend/src/pages/NotFound.tsx)
- `A` [frontend/src/pages/SignIn.tsx](../frontend/src/pages/SignIn.tsx)
- `A` [frontend/src/services/api.ts](../frontend/src/services/api.ts)
- `A` [frontend/src/services/completionAction.test.ts](../frontend/src/services/completionAction.test.ts)
- `A` [frontend/src/services/completionAction.ts](../frontend/src/services/completionAction.ts)
- `A` [frontend/src/services/httpApi.test.ts](../frontend/src/services/httpApi.test.ts)
- `A` [frontend/src/services/httpApi.ts](../frontend/src/services/httpApi.ts)
- `A` [frontend/src/services/queryClient.ts](../frontend/src/services/queryClient.ts)
- `A` [frontend/src/services/session.test.ts](../frontend/src/services/session.test.ts)
- `A` [frontend/src/services/session.ts](../frontend/src/services/session.ts)
- `A` [frontend/src/styles.css](../frontend/src/styles.css)
- `A` [frontend/src/styles/auth.css](../frontend/src/styles/auth.css)
- `A` [frontend/src/styles/dashboard.css](../frontend/src/styles/dashboard.css)
- `A` [frontend/src/styles/hr.css](../frontend/src/styles/hr.css)
- `A` [frontend/src/types/api.ts](../frontend/src/types/api.ts)
- `A` [frontend/src/types/domain.ts](../frontend/src/types/domain.ts)
- `A` [frontend/src/types/transport.ts](../frontend/src/types/transport.ts)
- `A` [frontend/src/utils/formatReadiness.ts](../frontend/src/utils/formatReadiness.ts)
- `A` [frontend/src/vite-env.d.ts](../frontend/src/vite-env.d.ts)
- `A` [frontend/tsconfig.app.json](../frontend/tsconfig.app.json)
- `A` [frontend/tsconfig.json](../frontend/tsconfig.json)
- `A` [frontend/tsconfig.node.json](../frontend/tsconfig.node.json)
- `A` [frontend/vite.config.ts](../frontend/vite.config.ts)

Логические implementation commits:

- `265a2e8` — feat: connect frontend to backend API
- `1cdd34b` — feat: add career recommendations and completion UI
- `6659ba5` — feat: add HR analytics and dataset management UI
- `92d79dd` — test: add frontend integration coverage

Этот отчёт, results JSON и README входят в завершающий docs commit;
его hash указан в итоговом сообщении. Полный журнал:

```sh
git log --first-parent --oneline 3a90322..HEAD
git status
```
