# Integration Phase 1 — backend + recommendation engine

Фаза завершена на локальной ветке `codex/team-integration` в отдельном worktree:
`/Users/zhanibek/.codex/worktrees/team-integration/hack-7b100a71-garden`.

## Git и границы работ

- Основа: `origin/main` (`13e011111a95ae1f54ddbebb5aa60f6b321022af`).
- Объединена утверждённая ветка `zhanibek` (`81c2b8382d5e5aa4acb8cd951ed37459719fc131`).
- Merge commit: `254c5ea452870947d957ca682758a44c5061f9e9`.
- Единственный merge conflict: `.gitignore`, add/add. Сохранён полезный общий
  набор правил backend и engine: `.venv/`, `.runtime/`, Python caches,
  `.env`, `.env.*`, исключение `!.env.example`, `*.py[cod]`, `.DS_Store`.
  Итог совпадает с `.gitignore` основной ветки.
- После одобрения Phase 1 изменения сгруппированы в четыре checkpoint-коммита:
  runtime reconstruction, provider/API, integration tests и документация.
  Точные hashes доступны через `git log --first-parent --oneline -5`.
  Push не выполнялся. `main`, `zhanibek`, `feat-beka`, `feat/adilet` не изменялись.
- Исходный workspace остаётся на `zhanibek` с прежним untracked `data/`.
- Frontend не объединялся. Новые зависимости, дублирующий repository, loaders
  или модели Employee не создавались. Существующие backend-модели расширены
  метаданными completion; DTO результата использует контракты движка.

## Подключение и защита от повторного прироста

Endpoint проходит authorization, получает один repository view, передаёт
исходный assessment baseline, profiles, полный каталог, историю и as_of в
provider. Затем выполняются `recommend()`, необязательное обогащение объяснений
на языке сотрудника и валидация полного результата.

`employee.skills` и `last_review_date` не меняются при completion. Profile,
completion и engine используют одну функцию реконструкции навыков. Уже
вычисленные effective skills не подаются обратно как assessment baseline.
Readiness вычисляет только движок; completion сохраняет историю и receipt.
Повтор с тем же idempotency key возвращает прежний receipt, не добавляя gain
и не повышая version. Порядок и receipts переживают restart.

Сохранены scoring weights, формулы history, ranking и explanation logic.
Файлы engine config/scoring/engine/career/simulation и весь `backend/ai/`
побайтно совпадают с `zhanibek`. В engine изменена только временная граница
contracts/skills и её использование в eligibility/history. Сигнал history
runtime completion явно отмечается `date_basis=runtime_completed_on`.

## Временной контракт

- `completed_at`: реальный timezone-aware timestamp операции, сохранённый в UTC.
- `completed_on`: логический день активного snapshot. Официальный срез:
  `2026-10-01`. Это отдельные часы от календаря машины.
- `runtime_sequence`: монотонный серверный порядок внутри транзакции; сохраняет
  последовательность при одинаковых timestamps или откате часов и после restart.
- На одном логическом дне runtime-операции следуют после legacy-истории;
  capped gains применяются в сохранённом порядке.
- Runtime completion после загруженной оценки учитывается и на дне
  `last_review_date`; импортированной истории по-прежнему нужна дата строго
  после review. Неизвестные исторические timestamps не выдумываются.
- Metadata runtime_sequence нельзя передать через HTTP completion/upload.
  Старое runtime state v1 восстанавливается с сохранённым порядком без
  выдуманных timestamps; новый формат state — v2.

## Тестирование

Проверки выполнены на Python 3.13 в изолированной `.venv` из существующего
`requirements-dev.txt`.

| Набор | Результат |
|---|---:|
| Recommendation + AI, исходные тесты без изменений | 280 passed |
| Backend: 93 исходных + 9 новых проверок | 102 passed |
| Интеграция: 18 HTTP/repository + 25 temporal/runtime | 43 passed |
| Полный совместный pytest | **425 passed**, 10.61 s |

Команды:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests/recommendation
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_*.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/integration
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/integration/audit_phase1.py
```

Проверены HTTP authorization до snapshot, один snapshot на расчёт, весь
структурированный ответ, kk/ru/en, fallback без ключа, неизменность rank/score
после объяснений, caps, одинаковый день, день review, timezone, rollback часов,
restart, idempotency и атомарность. Append/replace проверены на новых arbitrary
employee IDs с активной repository version. Для всех 200 официальных сотрудников
backend projection совпадает с реконструкцией engine.

Обычные пустые состояния возвращают HTTP 200: E0006 → `no_next_grade`,
E0018 → `no_eligible_recommendations`; `target_satisfied` проверен отдельно.
Явно отключённый provider возвращает инфраструктурный 503.

Обнаружено одно некритичное предупреждение зависимости Starlette об устаревшем
alias AnyIO `BlockingPortal`. Падений тестов нет.

## Реальный backend demo

Запросы выполнены через FastAPI TestClient с реальным provider и временным
persisted repository, используя официальный датасет и отсутствующий OpenAI key.

| E0001 | До | После EV_005 |
|---|---|---|
| API Design | 2 | 3 |
| System Design | 1 | 2 |
| Readiness | 0.5897435897435898 | 0.6666666666666666 |
| Рекомендации | EV_005 #1; EV_036 #2 | EV_036 #1 |
| EV_036 score | 0.44852207603844657 | 0.5735220760384466 |
| Version | 1 | 2 |

EV_005 до completion имеет score `0.8587990735249423`. Объяснение — kk,
deterministic fallback. Assessment baseline и review date сохранены.
Retry вернул `replayed=true`, version 2 и тот же record/timestamp; навыки не
выросли снова. Restart дал тот же рекомендационный ответ и idempotent receipt.

E0004: Data Analyst/Middle → Product Manager/Middle. EV_026 допущен через
`audience_match=target_role`, attained grade остаётся Middle. Completion успешен,
readiness `0.42105263157894735 → 0.5263157894736842`, а EV_026 исчез из выдачи:
остались EV_021 и EV_027. Для target-only completion используется тот же
детерминированный допуск; grade, prerequisites, availability и полезность не
обходятся. Тесты также проверяют отрицательные случаи.

## Датасет и передача frontend

Все 7 SHA-256 совпали до/после demo. `git diff origin/main -- data` пустой.
Dataset не редактировался и не добавлялся заново: использована уже отслеживаемая
основной веткой версия. Полные hashes и ответы сохранены в артефактах:

- [Итоговый API-контракт для Adilet](FRONTEND_API_CONTRACT.md).
- [Полный реальный GET recommendations для E0001](e0001-recommendations.response.json).
- [Все HTTP результаты, до/после, retry, restart и hashes](integration-phase1-results.json).

При подготовке checkpoint контракт повторно сверен с backend. Исправлены только
документальные неточности: HTTP 422 для бизнес-отказов completion, точные поля
career_state и единицы recommendation score. Уточнены допустимые типы мероприятий
для completion score и отсутствие HTTP login/identity endpoint. HTTP-пробы
подтвердили 422 для audience mismatch/unsupported score и 404 для `/auth/login`
и `/me`, не изменяя repository version. Поведение приложения не менялось.

## Оставшиеся ограничения

Блокирующих проблем в пределах Phase 1 не обнаружено. Рабочий режим persistence
предполагает один server worker. Демонстрация completion использует логический
день snapshot, включая эффект будущих scheduled events; она не удостоверяет
фактическое посещение будущей сессии. Это явно отражено в API-контракте.

Сетевой вызов OpenAI с реальным ключом в интеграционном demo не выполнялся;
fallback проверен через HTTP, режимы API failure/timeout/invalid output —
существующими AI-тестами. Frontend интеграция и объединение в main ожидают
отдельного одобрения. Реализация остановлена на завершении Phase 1.

## Точный список файлов

Списки ниже разделяют уже утверждённые файлы Steps 1–4, перенесённые merge,
и новые изменения Phase 1 после merge. Путь указан относительно repository.

### Phase 1: изменены (19)

- [backend/api/employees.py](../backend/api/employees.py)
- [backend/data/loader.py](../backend/data/loader.py)
- [backend/data/repository.py](../backend/data/repository.py)
- [backend/data/validation.py](../backend/data/validation.py)
- [backend/integrations/recommendations.py](../backend/integrations/recommendations.py)
- [backend/main.py](../backend/main.py)
- [backend/models/domain.py](../backend/models/domain.py)
- [backend/recommendation/contracts.py](../backend/recommendation/contracts.py)
- [backend/recommendation/eligibility.py](../backend/recommendation/eligibility.py)
- [backend/recommendation/history.py](../backend/recommendation/history.py)
- [backend/recommendation/skills.py](../backend/recommendation/skills.py)
- [backend/services/activity_service.py](../backend/services/activity_service.py)
- [backend/services/recommendation_service.py](../backend/services/recommendation_service.py)
- [backend/services/skill_projection.py](../backend/services/skill_projection.py)
- [docs/API.md](../docs/API.md)
- [docs/INTEGRATION.md](../docs/INTEGRATION.md)
- [pytest.ini](../pytest.ini)
- [tests/conftest.py](../tests/conftest.py)
- [tests/test_recommendations.py](../tests/test_recommendations.py)

### Phase 1: добавлены (9)

- [backend/integrations/engine_inputs.py](../backend/integrations/engine_inputs.py)
- [backend/integrations/recommendation_provider.py](../backend/integrations/recommendation_provider.py)
- [docs/FRONTEND_API_CONTRACT.md](../docs/FRONTEND_API_CONTRACT.md)
- [docs/e0001-recommendations.response.json](../docs/e0001-recommendations.response.json)
- [docs/integration-phase1-audit.md](../docs/integration-phase1-audit.md)
- [docs/integration-phase1-results.json](../docs/integration-phase1-results.json)
- [tests/integration/audit_phase1.py](../tests/integration/audit_phase1.py)
- [tests/integration/test_backend_engine.py](../tests/integration/test_backend_engine.py)
- [tests/integration/test_runtime_contract.py](../tests/integration/test_runtime_contract.py)

### Перенесены готовыми из zhanibek через merge (43)

- [backend/ai/__init__.py](../backend/ai/__init__.py)
- [backend/ai/config.py](../backend/ai/config.py)
- [backend/ai/contracts.py](../backend/ai/contracts.py)
- [backend/ai/explanations.py](../backend/ai/explanations.py)
- [backend/ai/openai_client.py](../backend/ai/openai_client.py)
- [backend/ai/templates.py](../backend/ai/templates.py)
- [backend/recommendation/__init__.py](../backend/recommendation/__init__.py)
- [backend/recommendation/career.py](../backend/recommendation/career.py)
- [backend/recommendation/config.py](../backend/recommendation/config.py)
- [backend/recommendation/contracts.py](../backend/recommendation/contracts.py)
- [backend/recommendation/eligibility.py](../backend/recommendation/eligibility.py)
- [backend/recommendation/engine.py](../backend/recommendation/engine.py)
- [backend/recommendation/history.py](../backend/recommendation/history.py)
- [backend/recommendation/scoring.py](../backend/recommendation/scoring.py)
- [backend/recommendation/simulation.py](../backend/recommendation/simulation.py)
- [backend/recommendation/skills.py](../backend/recommendation/skills.py)
- [docs/explanations-contract.md](../docs/explanations-contract.md)
- [docs/recommendation-contract.md](../docs/recommendation-contract.md)
- [docs/step1-results.json](../docs/step1-results.json)
- [docs/step2-audit.md](../docs/step2-audit.md)
- [docs/step2-results.json](../docs/step2-results.json)
- [docs/step3-audit.md](../docs/step3-audit.md)
- [docs/step3-results.json](../docs/step3-results.json)
- [docs/step4-audit.md](../docs/step4-audit.md)
- [docs/step4-results.json](../docs/step4-results.json)
- [tests/recommendation/audit_step2.py](../tests/recommendation/audit_step2.py)
- [tests/recommendation/audit_step3.py](../tests/recommendation/audit_step3.py)
- [tests/recommendation/audit_step4.py](../tests/recommendation/audit_step4.py)
- [tests/recommendation/test_career.py](../tests/recommendation/test_career.py)
- [tests/recommendation/test_config.py](../tests/recommendation/test_config.py)
- [tests/recommendation/test_dataset.py](../tests/recommendation/test_dataset.py)
- [tests/recommendation/test_eligibility.py](../tests/recommendation/test_eligibility.py)
- [tests/recommendation/test_engine.py](../tests/recommendation/test_engine.py)
- [tests/recommendation/test_explanation_templates.py](../tests/recommendation/test_explanation_templates.py)
- [tests/recommendation/test_explanations.py](../tests/recommendation/test_explanations.py)
- [tests/recommendation/test_history.py](../tests/recommendation/test_history.py)
- [tests/recommendation/test_openai_client.py](../tests/recommendation/test_openai_client.py)
- [tests/recommendation/test_scoring.py](../tests/recommendation/test_scoring.py)
- [tests/recommendation/test_simulation.py](../tests/recommendation/test_simulation.py)
- [tests/recommendation/test_skills.py](../tests/recommendation/test_skills.py)
- [tests/recommendation/test_step2_dataset.py](../tests/recommendation/test_step2_dataset.py)
- [tests/recommendation/test_step3_dataset.py](../tests/recommendation/test_step3_dataset.py)
- [tests/recommendation/test_step4_dataset.py](../tests/recommendation/test_step4_dataset.py)

`.gitignore` участвовал в разрешении merge conflict, но итогового diff к `origin/main` нет.
