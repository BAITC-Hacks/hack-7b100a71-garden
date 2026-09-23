# Career Quest — контракт frontend после Integration Phase 1

Backend подключён к детерминированному движку и объяснениям. Frontend в этой
фазе не объединялся и не реализовывался. Этот контракт предназначен для Adilet.

## Адреса, авторизация, единицы

Пути начинаются с `/employees`, `/activities`, `/events`, `/skills`,
`/role-profiles`, `/hr`, `/datasets`: префикса `/api` нет. Базовый адрес задаётся
конфигурацией frontend. Ключи OpenAI и HR не включаются в сборку `VITE_*`.

Защищённые запросы передают `Authorization: Bearer <token>`. Employee token
разрешает собственные profile/history/recommendations/completion. HR token
разрешает всех сотрудников, directory, аналитику и импорт. `/health` публичен.
Глобальный selector сотрудников доступен только HR. Отключённая авторизация —
отдельная backend-настройка демо, не действие HTTP-адаптера frontend.

В Phase 1 нет `/auth/login` или `/me`: эти запросы возвращают 404. Bearer token
непрозрачный; извлечь из него роль или employee_id нельзя. Для навигации frontend
должен получить заранее настроенную demo identity (`role`: employee/hr,
`employee_id` для сотрудника) вместе с соответствующим токеном при входе в демо.
Это клиентский контекст, а не HTTP response; backend независимо проверяет доступ
по своему mapping токенов. Не включать общий список токенов в frontend-сборку.

- Уровни навыков: целые 0–5; отсутствующий в baseline навык означает 0 для расчёта.
- Readiness, recommendation score и normalized factors: 0–1. Проценты — только форматирование UI.
- Duration: `duration_hours`; для минут умножить на 60.
- Calendar dates: `YYYY-MM-DD`; не интерпретировать как случайный локальный midnight.
- `completed_at`: ISO timestamp с часовым поясом, сериализуется в UTC.
- Идентификаторы — непрозрачные строки; не привязывать UI к E0001 или числу 200.

Обычный envelope — `{ "data": ..., "meta": ... }`. У рекомендаций и completion
версия находится в `data.version`; верхнего `meta` у этих ответов нет. Не добавлять
фиктивные поля при нормализации. Версия — целое число активного repository snapshot.

## Профиль, каталог, история

| Запрос | Содержимое `data` |
|---|---|
| `GET /employees?offset=0&limit=50` | Список baseline Employee; HR only |
| `GET /employees/{id}` | `{employee, role_profile, effective_skills}` |
| `GET /employees/{id}/history?offset=0&limit=50` | ActivityRecord[] |
| `GET /skills` | Skill[]: skill_id, name, type, category, description |
| `GET /events` | Полные Event[] |
| `GET /events/{event_id}` | Полный Event |
| `GET /role-profiles` | RoleProfile[] |
| `GET /role-profiles/{role}/{grade}` | RoleProfile; role URL-encode |

Списки имеют `meta: {version, as_of_date, total, offset, limit}`. Максимальный
limit — 500. Первый page не является полным каталогом: учитывать `total`.
Подробный профиль/мероприятие имеют `meta: {version, as_of_date}`.

Employee содержит `employee_id`, `full_name`, `department`, `role`, `grade`,
`manager_id`, `hire_date`, `tenure_months`, `work_format`, `preferred_language`,
`career_goal`, `skills`, `last_review_date`. `employee.skills` — оценка на review;
для отображения текущего прогресса используется `effective_skills`.
`role_profile` в profile response относится к текущим role/grade, не к цели.

ActivityRecord содержит `record_id`, `employee_id`, `event_id`, `date`,
`due_date`, `status`, `completion_pct`, `score`, `feedback_rating`, `assigned_by`
и nullable completion metadata: `completed_on`, `completed_at`, `runtime_sequence`.
Не считать `date` временем последнего изменения: это enrollment/session date.
Показывать попытки по `record_id`, не объединять их по `event_id`.
Статусы: completed, in_progress, dropped, no_show, declined, overdue.

## Рекомендации, career state и объяснения

`GET /employees/{employee_id}/recommendations` возвращает полный существующий
результат движка с объяснениями и `version`. Backend проверяет его структуру и
ссылки, не меняет порядок, оценки и evidence. Данные берутся из одного view.

| Поле `data` | Значение |
|---|---|
| employee_id, as_of, version | Сотрудник, логическая дата расчёта, версия snapshot |
| status | ok / no_eligible_recommendations / no_next_grade / target_satisfied / invalid_target_requirements |
| target | null либо `{role, grade, source: career_goal|next_grade}` |
| career_readiness | null либо подробный ReadinessResult, scalar в `.current` |
| skill_gaps | `{skill_id,current,required,gap,critical}[]` |
| career_state | employee_id/as_of/status/target/skill_gaps/career_readiness/skills_reconstruction |
| candidate_count | Число всех допустимых кандидатов до Top 3 |
| recommendation_count | Число возвращённых рекомендаций, 0–3 |
| recommendations | Упорядоченный список RankedRecommendation с explanation |
| blocked_summary | null либо причины отсутствия рекомендаций и непокрытые дефициты |
| explanation_summary | Локализованное объяснение общего состояния |
| explanation_meta | Язык, флаг fallback и исход необязательного OpenAI |

`career_readiness.current` — покрытие требований цели, не гарантия повышения.
Объект также сохраняет `status`, `reason`, `critical_weight`,
`weighted_covered_levels`, `weighted_required_levels`,
`critical_requirements_met`, `remaining_critical_gaps`, `all_requirements_met`.

В каждой рекомендации сохраняются:

| Поле | Назначение |
|---|---|
| rank, event_id, title, score | Готовый порядок и оценка; frontend не пересортировывает |
| factors | Для каждого фактора raw, normalized, weight, contribution |
| scoring_evidence | Полезный/общий прирост, effort, availability, нормализаторы пула |
| simulation | Полные skills/gaps before/after, reductions, закрытые требования, readiness before/after |
| evidence | current/target role, audience_match, attained_grade, prerequisites, history, availability, estimate flag |
| history_signals | compatibility, feedback_signal, агрегированные исходные доказательства |
| explanation | language, source, text, facts, segments |

Точные вложенные структуры имеют единственный исходный контракт в
[`backend/recommendation/contracts.py`](../backend/recommendation/contracts.py)
и [`backend/ai/contracts.py`](../backend/ai/contracts.py). Backend DTO использует
эти объявления, а не отдельную копию модели расчётов.

`career_state.skills_reconstruction` содержит `effective_skills`, applied record
IDs, skill changes, uncertain IDs, warnings, date_policy, is_estimate. Сохранять
предупреждения и явно показывать приблизительность исторической реконструкции.

`blocked_summary` содержит `rejection_counts`, `event_rejections`,
`uncovered_target_gaps`, `useful_blocked_events`. Причины могут пересекаться;
сумма счётчиков не равна числу мероприятий.

Язык берётся из `employee.preferred_language` (kk/ru/en). Отдельного HTTP language
override в Phase 1 нет. Explanation.source — deterministic или openai. OpenAI
выбирает только разрешённые варианты фраз; итоговые факты собираются локально.
Без ключа ответ остаётся HTTP 200 с `provider_status=missing_api_key` и fallback.
Все остальные режимы/ограничения описаны в
[контракте объяснений](explanations-contract.md).

Отдельные endpoint для career state и explanation не нужны: они уже включены
в рекомендационный ответ. Trajectory UI может отобразить текущую позицию и
серверную цель; история прошлых должностей/гарантированных будущих повышений
не предоставляется. Не придумывать категорию careerImpact=High из score.

Полный, не сокращённый реальный HTTP-ответ E0001 до completion:
[`e0001-recommendations.response.json`](e0001-recommendations.response.json).
Он получен через FastAPI TestClient с repository официального датасета,
включённым реальным provider и отключённой сетью OpenAI через отсутствие ключа.

## Completion и последующее обновление

```http
POST /activities/{event_id}/complete
Authorization: Bearer <token>
Idempotency-Key: <one key per user action>
Content-Type: application/json
```

```json
{"employee_id":"E0001"}
```

Опциональные поля: `record_id`, `score` (0–100), `feedback_rating` (1–5).
`score` принимается только для course/certification/compliance; для других типов
возвращается `422 score_not_supported`.
При нескольких active assignments нужен record_id. Completion timestamps,
runtime_sequence, навыки, readiness и роль клиента в body не принимаются.

`data` ответа содержит `activity`, `effective_skills`,
`skill_changes: [{skill_id,before,after,gain,event_gain,max_level}]`,
`version`, `replayed`. Один ключ повторно использовать только с идентичным body.
При retry возвращается исходный receipt с `replayed=true`, без нового gain и
без новой версии. Если позже были другие действия, receipt может иметь старую
версию: актуальное состояние следует читать GET-запросами.

После success/refetch инвалидировать profile, history, recommendations и HR.
Следующий GET recommendations использует новую версию и пересчитывает career
state, допуск, весь пул скоринга и объяснения. Не прибавлять gain локально и не
считать readiness на frontend. Для согласованного экрана сопоставлять версии
ответов; при 409 dataset_changed повторять чтение.

Для target-only перехода backend использует детерминированный evaluate_event;
роль назначения допустима только при явной career_goal, а грейд допуска остаётся
текущим достигнутым. Авторизация и ограничения prerequisites не обходятся.

## Временной контракт демо и persistence

Это приложение работает на логическом дне активного датасета. У официального
среза это 2026-10-01; календарь машины может отличаться.

- `completed_at` нового runtime completion — реальный timezone-aware timestamp
  операции, нормализованный в UTC. Он не подгоняется под дату фикстуры.
- `completed_on` — логический business day snapshot, на котором применяется
  событие в этом демо. Он явно отличается от фактического времени записи.
- `runtime_sequence` — порядок операций, назначенный сервером внутри транзакции.
  Он определяет порядок при совпадении/откате часов, а также сохраняется после restart.
- На одной логической дате runtime-операции следуют после датированной legacy
  истории по принятому правилу упорядочивания; импорту не приписывается точное время.
- Новые runtime-операции выполняются после загруженной оценки и учитываются даже
  на её календарном дне. У обычной импортированной истории сохраняется граница
  completion_date > last_review_date. Baseline и last_review_date не меняются.
- Profile, completion, HR и engine используют одну reconstruction-функцию.
  Effective skills никогда не подставляются повторно в employee.skills.

`runtime_sequence` нельзя задать через upload или completion HTTP body. Старое
runtime state v1 восстанавливается с его сохранённым порядком, без создания
несуществующих точных timestamps. Новое state имеет schema_version=2. Путь state
отдельный от source dataset; нужен один server worker. Dataset replace сбрасывает
старые receipts/runtime order, append сохраняет их.

Кнопка завершения будущего scheduled event в этом режиме демонстрирует эффект
завершения на срезе; она не удостоверяет, что будущая сессия действительно уже
прошла. Проверка реального посещения/календаря не добавлялась в Phase 1.

## HR и загрузка датасета

`GET /hr/analytics` возвращает employee_count, gap_basis, common_skill_gaps,
employees_without_next_step, activity_participation, participation_summary.
Gap basis — effective skills против **текущих role/grade**, не карьерной цели.
Coverage содержит available/count/evaluated_count/pending_count/complete.
Без полной оценки count может быть null; pending нельзя отображать как ноль.
Default provider не выполняет массовые AI-запросы ради HR: coverage отражает
известные кэшированные расчёты. Новые employeesInDevelopment/participationRate
в этом контракте не определялись.

`POST /datasets/validate?mode=append|replace` и
`POST /datasets/upload?mode=append|replace` принимают multipart:
`employees_file`, `activity_history_file`, `events_file`, `skills_file`.

- Append: новые employees/history; совпадающая metadata; duplicate IDs не upsert.
- Replace: четыре файла вместе; новый каталог и профильный набор.
- Validate: `{data:{valid,counts,errors:[{code,location,message}],mode,version}}`.
- Upload: `{data:{uploaded,mode,counts,version}}`; повторная атомарная валидация.
- validationId не существует. При ошибке upload исходный snapshot сохраняется.
- После upload инвалидировать все snapshot-зависимые queries.

Рекомендации используют активный repository после импорта, независимо от пути
initial dataset. Для нового employee login токен настраивается отдельно; HR
может открыть импортированные профили сразу.

## Ошибки и обязательные UI состояния

Ошибка: `{error:{code,message,details}}`. Сохранять backend code, HTTP status и
структурированные details, не сводить всё к NETWORK.

| HTTP | Значение |
|---|---|
| 200 | Включая нормальные пустые рекомендации и результат validate с valid=false |
| 401 / 403 | Нет аутентификации / нет доступа |
| 404 | Неизвестный сотрудник, мероприятие или participation |
| 409 | Idempotency conflict, duplicate completion, ambiguous assignment, изменившийся snapshot |
| 413 / 422 | Слишком большой upload / некорректный запрос или датасет |
| 502 | Provider вернул некорректный результат или упал |
| 503 | Provider отсутствует / недоступна инфраструктура |
| 504 | Истёк backend deadline рекомендации |

Отказы completion по audience/prerequisites/eligibility возвращают 422 с конкретным code
(например, event_audience_mismatch, prerequisites_not_met, event_not_eligible).
OpenAI failure сам по себе не является ошибкой endpoint: используется fallback.

Полные до/после, completion receipts, restart и E0004:
[`integration-phase1-results.json`](integration-phase1-results.json).
