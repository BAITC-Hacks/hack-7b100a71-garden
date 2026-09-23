# Career Quest: контракт детерминированных рекомендаций — шаги 1–3

Реализованы контракты/конфигурация, определение цели, восстановление навыков,
целевые дефициты и готовность, допуск к мероприятиям и независимая симуляция
их влияния, сигналы истории, семь факторов оценки и ранжирование Top 1–3.
Контракты шагов 1–2 сохранены. OpenAI и генерация пояснений пока не реализованы.

## Ответственность команды

| Участник | Ветка | Ответственность |
|---|---|---|
| Zhanibek | `zhanibek` | Рекомендации, скоринг, готовность, доказательства, AI-пояснения, финальная интеграция |
| Bekarys | `feat-beka` | FastAPI, загрузка/валидация, доступ к данным, Pydantic-модели, API и хранение завершений, HR-аналитика, импорт |
| Adilet | `feat/adilet` | React, интерфейс сотрудника, траектория, рекомендации, HR-панель, интерфейс импорта |

Бекарыс передаёт проверенные данные через адаптер; Адилет получает результат
через его API. Этот пакет не содержит HTTP, файлового ввода-вывода, хранения,
Pydantic-моделей или зависимостей OpenAI. Для шагов 1–3 достаточно Python 3.9+
и стандартной библиотеки. Файлы зависимостей не создавались.

## Вызов из backend

```python
from backend.recommendation.career import build_career_state

result = build_career_state(
    employee=employee_mapping,
    role_profiles=skills_document["role_profiles"],
    events=events_document["events"],
    history=history_rows,
    as_of=skills_document["meta"]["as_of_date"],
)
```

Функции получают обычные словари и списки, а не JSON-обёртки. Дополнительные
поля backend игнорируются. История может содержать всех сотрудников или только
выбранного. Дата среза задаётся явно; системные часы не используются.
В официальных данных дата равна `2026-10-01`.

`contracts.py` описывает минимальную границу расчёта через TypedDict, без
дублирования прикладных моделей. Backend отвечает за полную валидацию импорта,
включая глобальную уникальность ID, ссылки на каталог навыков и сочетания
status/completion_pct. Расчёт дополнительно защищает арифметику, ссылки на
используемые события и хронологию. Ошибки границы —
`RecommendationInputError`, содержащие `.code` и понятное сообщение; перевод
в HTTP-ошибки остаётся в backend.

Можно вызывать отдельно `resolve_target`, `calculate_skill_gaps`,
`calculate_readiness` из `career.py` и `reconstruct_effective_skills` из
`skills.py`. Входные объекты не изменяются; повторный расчёт начинается с
неизменённого базового состояния.

## Цель и дефициты

Явный `career_goal` проверяется первым, включая переходы Lead. При null
выбирается следующий существующий грейд той же роли. Для последнего грейда
возвращается `no_next_grade`. Неизвестная цель не заменяется молча.

Критические навыки берутся ровно из целевого профиля. Они не объединяются
с предыдущими грейдами. Дефициты текущего грейда допустимы и не меняют грейд.
Отсутствующий навык имеет уровень 0.

`skill_gaps` содержит только положительные дефициты: `skill_id`, `current`,
`required`, `gap`, `critical`. Порядок: критические первыми, затем больший
дефицит, затем идентификатор. Уровни/требования — целые числа 0–5; bool
не принимается как уровень.

## Восстановление навыков и ограничения дат

Исходные навыки отражают `last_review_date`. Применяются завершённые
участия после этой даты и не позже даты среза. Участия на дате оценки
повторно не начисляются. День среза включается целиком.

```text
gain_applied = min(gain, max(0, max_level - current))
after = current + gain_applied
```

Уровень выше предела события не снижается. Поддерживаются нулевой и
многобалльный целочисленный gain. Score и completion_pct не масштабируют gain:
статус completed является основанием начисления после проверки входа backend.
Обязательный онбординг сохраняет свои эффекты. Разные участия одного события
остаются разными; идентичный повтор record_id обрабатывается один раз,
противоречащий повтор отклоняется. Запрет повторных рекомендаций применяется
отдельным правилом допуска шага 2, без удаления фактической истории.

В официальном CSV date — дата сессии или зачисления/назначения для self_paced.
Точной даты завершения нет. Политика совместимости `participation_date_proxy`:

- У завершённых записей после оценки используется доступная дата участия.
- Старые self_paced-зачисления с неизвестным временем завершения не начисляются
  повторно и возвращаются в `uncertain_record_ids`.
- Результат с применёнными датами-заменителями либо неоднозначными записями
  получает `is_estimate=true`. Это не гарантированно точное состояние и не
  гарантированная нижняя граница: реальный порядок завершений может отличаться.
- Участия без develops_skills не входят в applied_record_ids. Записи с навыками,
  чей прирост полностью ограничен cap, входят; изменения с gain_applied=0
  сохраняются для объяснения.

Для новых завершений Бекарыс может передать необязательное поле `completed_at`:
ISO-дата/время либо объект date/datetime. Оно имеет приоритет над date, в том
числе когда зачисление было до оценки. Фактический timestamp хранит backend;
исходный датасет не переписывается. completed_at допускается только для
completed и не может предшествовать участию.

Границы оценки/среза используют календарную дату, указанную в timestamp.
Для порядка timestamp приводится к UTC; значение без часового пояса
интерпретируется как UTC только для сортировки. Даты без времени используют
начало суток, затем record_id; пересекающиеся интервалы с общими навыками
помечаются предупреждением о неизвестном порядке. Backend должен передавать
timezone-aware timestamps для точных новых завершений. last_review_date и
as_of — календарные даты, а не timestamps.

Доказательства реконструкции: `effective_skills`, `applied_record_ids`,
`skill_changes` с before/after/gain_applied/date_basis,
`uncertain_record_ids`, структурированные `warnings`, `date_policy`,
`is_estimate`. `date_basis` каждого эффекта: completed_at, session_date либо
enrollment_date. `date_policy` обозначает резервную политику, а не источник
даты каждого отдельного эффекта.

## Готовность

```text
w = readiness_critical_weight для критических навыков, иначе 1
coverage = sum(w * min(current, required)) / sum(w * required)
```

Множитель критических навыков по умолчанию 2. Это покрытие требований цели,
не гарантия повышения. Избыточный уровень не компенсирует другой дефицит.

Результат содержит current (0–1, без округления), critical_weight,
weighted_covered_levels, weighted_required_levels, critical_requirements_met,
remaining_critical_gaps и all_requirements_met. Пустые/нулевые требования дают
status=unavailable, reason=no_positive_requirements и null для процента/флагов.
UI должен учитывать skills_reconstruction.is_estimate при отображении метрики.

Общий результат build_career_state содержит employee_id, as_of, target,
skill_gaps, career_readiness, skills_reconstruction и status:

- ok — цель рассчитана, остались дефициты;
- target_satisfied — реконструированные навыки покрывают требования;
- no_next_grade — Lead без явной цели, target/readiness равны null;
- invalid_target_requirements — невозможно вычислить готовность.

## Централизованная конфигурация

Все настройки находятся в config.py. Объекты неизменяемы; для настройки
используется dataclasses.replace(DEFAULT_CONFIG, readiness_critical_weight=3).
Новые настройки не меняют значения по умолчанию.

| Настройки | Значения по умолчанию |
|---|---|
| Грейды | Junior, Middle, Senior, Lead |
| Шкала | 0–5, отсутствующий навык = 0 |
| Критический вес готовности | 2 |
| Веса скоринга | critical .35, gap .25, relevance .15, history .10, feedback .05, effort .05, availability .05 |
| Сходство истории | навыки .60, тип .25, формат .15 |
| Давность | период полураспада 365 дней |
| Сглаживание H | prior_weight 2, neutral_value .5 |
| Сглаживание F | feedback_prior_weight 2, feedback_neutral_value .5 |
| Источник назначения | self 1, manager .5, hr .25; unknown_source_weight .5 |
| Диагностика недавнего сходного участия | recent_window_days 365, recent_similarity_threshold .5; не меняет H/F |
| Исходы | completed 1, dropped .25, no_show 0, declined .40 |
| Исключение из истории предпочтений | in_progress, overdue, обязательные события |
| Доступность | масштаб ожидания 30 дней |
| Повторяемые рекомендации | EV_036 — документированное исключение |

Скоринг использует эти настройки и сохраняет исходные доказательства допуска
и влияния рядом с нормализованными факторами. `ScoringWeights` проверяет
допустимость весов и сумму 1; `HistoryConfig` проверяет коэффициенты сходства,
диапазоны, положительные веса сглаживания и период полураспада. Вложенные
настройки также меняются через `dataclasses.replace`.

## Шаг 2: вызовы допуска и симуляции

Публичные функции доступны как обычный Python-код. В `eligibility.py`:

```python
def evaluate_event(
    employee: Mapping,
    career_state: Mapping,
    target_profile: Optional[Mapping],
    event: Mapping,
    history: Sequence,
    *,
    as_of: CalendarDate,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> EligibilityResult: ...

def evaluate_catalog(
    employee: Mapping,
    career_state: Mapping,
    role_profiles: Sequence,
    events: Sequence,
    history: Sequence,
    *,
    as_of: CalendarDate,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> CatalogEligibility: ...
```

В `simulation.py`:

```python
def simulate_event(
    effective_skills: Mapping,
    target_profile: Mapping,
    event: Mapping,
    *,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> EventSimulation: ...
```

`CalendarDate` — ISO-строка даты либо объект `datetime.date`. `Mapping` и
`Sequence` обозначают обычные словари и последовательности. Результаты —
JSON-совместимые словари; типы `EligibilityResult`, `CatalogEligibility` и
`EventSimulation` объявлены через TypedDict в `contracts.py`.

Пример продолжения вызова шага 1:

```python
from backend.recommendation.eligibility import evaluate_catalog

admission = evaluate_catalog(
    employee=employee_mapping,
    career_state=result,
    role_profiles=skills_document["role_profiles"],
    events=events_document["events"],
    history=history_rows,
    as_of=skills_document["meta"]["as_of_date"],
)
```

`evaluate_event` получает профиль, соответствующий разрешённой цели;
если цели нет, нужно передать `target_profile=None`. `evaluate_catalog`
находит профиль в переданном списке. Минимальный `EligibilityEventInput`
добавляет к `EventInput` поля `mandatory`, `target_roles`, `target_grades`,
`prerequisites`, `upcoming_sessions`; `title` необязателен и заменяется
идентификатором события при отсутствии.

Вызывающий backend должен **пересобрать CareerState после изменения истории,
навыков, карьерной цели, даты среза или параметров расчёта**. Шаг 2 использует
готовые эффективные навыки и не восстанавливает их повторно. Проверяются
совпадение сотрудника, даты среза, цели и целевого профиля, а также вес
критических навыков. Эти проверки не заменяют обновление состояния после
изменений данных. На обоих шагах следует передавать одну конфигурацию.

## Правила допуска и причины отказа

Допуск по роли возможен через текущую роль либо **явную** целевую роль
из `career_goal`. Допуск через целевую роль — политика приложения для
карьерных переходов, а не дополнительное правило официального README.
`audience_match` различает основания:

- `current_role` — совпала только текущая роль;
- `target_role` — совпала только явная целевая роль;
- `both` — совпали обе проверки, в том числе при явной цели внутри той же роли;
- `null` — ни одно основание не совпало.

Для автоматически определённой цели `next_grade` отдельное основание
`target_role` не применяется. Грейд допуска всегда равен **достигнутому
текущему грейду сотрудника**. Желаемый грейд его не заменяет.

Каждое предварительное требование проверяется по эффективным навыкам из
CareerState. Отсутствующий навык равен нулю. Мероприятие должно сокращать
хотя бы один дефицит целевого профиля после ограничений `gain/max_level`.
Рост постороннего навыка либо рост выше уже выполненного требования не
является полезным сокращением целевого дефицита.

`rejection_reasons` содержит объекты `{code, message}`. Все безопасные
проверки выполняются: у мероприятия может быть несколько причин отказа.

| Код | Условие отказа |
|---|---|
| `MANDATORY` | Обязательное мероприятие не является кандидатом для рекомендации |
| `ROLE_MISMATCH` | Не совпала ни текущая, ни явная целевая роль |
| `GRADE_MISMATCH` | Текущий достигнутый грейд не входит в аудиторию |
| `PREREQUISITE_NOT_MET` | Хотя бы один требуемый навык ниже порога |
| `ALREADY_COMPLETED` | Добровольное неповторяемое мероприятие уже завершено |
| `ALREADY_IN_PROGRESS` | Есть отдельное незавершённое участие `in_progress` |
| `NO_TARGET_GAP_IMPACT` | Гипотетическое завершение не уменьшает целевые дефициты |
| `NO_UPCOMING_SESSION` | Для мероприятия по расписанию нет сессии на дату среза или позже |
| `NO_CAREER_TARGET` | У сотрудника нет разрешённой карьерной цели |

`eligible=true` означает пустой список причин. Некорректные входные данные
приводят к `RecommendationInputError`; они не маскируются бизнес-причиной отказа.
При отсутствии цели все события отклоняются с `NO_CAREER_TARGET`, их
`simulation=null`; остальные независимые проверки продолжаются.
`NO_TARGET_GAP_IMPACT` в этом случае не добавляется.

Завершения учитываются для запрета повтора и до, и после `last_review_date`.
Повторяемые события задаются в `config.recurring_event_ids`, по умолчанию
`("EV_036",)`. Исключение снимает только запрет по завершению; все остальные
проверки сохраняются. Обязательные завершения не получают причину
`ALREADY_COMPLETED`: к ним уже применяется `MANDATORY`.

Строки истории остаются отдельными участиями. Любое учитываемое
`in_progress` блокирует новую рекомендацию, даже если другая строка того же
мероприятия завершена. Идентичные повторы `record_id` учитываются один раз;
конфликтующие повторы отклоняются. Статусы `dropped`, `no_show`, `declined`
и `overdue` сами по себе не запрещают мероприятие. Оценка предпочтений по
этой истории на шаге 2 не вычисляется.

Для допуска используются факты не позже явно заданной даты среза.
Если `date` либо переданный `completed_at` позже среза, запись попадает в
`ignored_future_record_ids` и не блокирует рекомендацию. `completed_at`
допускается только для завершённой записи и не может предшествовать участию.
Для старых записей без него сохраняются описанные выше ограничения дат;
неизвестное время завершения не выдумывается.

`self_paced` доступен без сессий: `next_session_date=null`,
`days_until_next_session=0`. Для `online` и `offline` выбирается самая ранняя
сессия с датой `>= as_of`. Прошедшие даты исключаются; остальные сортируются
и очищаются от повторов. При отсутствии будущих сессий дата и ожидание равны
`null`. Системные часы нигде не используются.

## Доказательства допуска и результат каталога

`EligibilityResult` содержит `event_id`, `title`, `eligible`,
`rejection_reasons`, `evidence` и `simulation`.

| Поля в `evidence` | Содержание |
|---|---|
| `current_role`, `target_role`, `target_grade` | Текущая роль и разрешённая цель; поля цели равны null, если её нет |
| `audience_match` | `current_role`, `target_role`, `both` либо null |
| `attained_grade`, `matched_current_grade` | Текущий грейд и его совпадение с аудиторией; второе поле равно null при несовпадении |
| `prerequisite_checks` | Все требования: `skill_id`, `current`, `required`, `met`; порядок по ID навыка |
| `history` | `completed_record_ids`, `in_progress_record_ids`, `ignored_future_record_ids`, `recurring_exception` |
| `availability` | `format`, `available`, `self_paced`, `next_session_date`, `days_until_next_session`, `valid_session_dates` |
| `skills_are_estimated` | Значение `skills_reconstruction.is_estimate` из шага 1 |

`recurring_exception` показывает, разрешён ли повтор этого добровольного
события конфигурацией; он может быть true и до первого завершения.
Списки ID истории отсортированы. Это факты для допуска, а не исторический скоринг.

`CatalogEligibility` содержит `employee_id`, `as_of`, `target`,
`event_count`, `eligible_count`, `rejected_count`, `eligible_candidates` и
`rejected_events`. Оба списка содержат полные `EligibilityResult` и упорядочены
по `event_id`. Это порядок воспроизводимого вывода, а не рейтинг. Каталог
может вернуть ноль, один, два либо больше подходящих мероприятий; правила
не ослабляются для получения трёх кандидатов.

## Независимая симуляция влияния

`simulate_event` не решает вопрос допуска и может вызываться для любого
корректного мероприятия с целевым профилем. `evaluate_event` и
`evaluate_catalog` возвращают симуляцию также для отклонённых мероприятий,
если цель существует. Это гипотетический эффект завершения, а не разрешение
на участие; интерфейс должен отдельно учитывать `eligible` и причины отказа.

Каждое мероприятие моделируется от одной и той же копии эффективных навыков.
Входные employee, CareerState, профиль и события не изменяются; возвращаемые
вложенные объекты не ссылаются на изменяемые входные объекты. Приросты
альтернатив нельзя складывать как готовый последовательный план.

Для каждой записи `develops_skills`, включая нерелевантные и полностью
ограниченные приросты, `skill_impact` возвращает `skill_id`, `before`,
`advertised_gain`, `max_level`, `after`, `actual_gain`:

```text
actual_gain = min(gain, max(0, max_level - before))
after = before + actual_gain
```

Уровень выше предела мероприятия сохраняется. В `target_skill_impact`
попадают только развиваемые навыки из требований целевого профиля, включая
навыки с нулевой полезностью. Поля: `skill_id`, `current`, `required`,
`gap_before`, `after`, `gap_after`, `useful_gain`, `critical`.

```text
gap_before = max(required - current, 0)
gap_after = max(required - after, 0)
useful_gain = gap_before - gap_after
```

`EventSimulation` также возвращает:

- `event_id`, `target={role, grade}`, `simulated_skills_after`;
- `skill_gaps_before`, `skill_gaps_after`, `critical_gaps_before`,
  `critical_gaps_after` — положительные дефициты всех требований, включая
  навыки, которых событие не касается;
- `total_gap_before`, `total_gap_after`, `total_gap_reduction` — суммы
  дефицитов в уровнях навыков и их сокращение;
- `critical_gap_before`, `critical_gap_after`, `critical_gap_reduction` —
  аналогичные суммы только для критических навыков целевого профиля;
- `requirements_closed`, `critical_requirements_closed` — отсортированные
  ID требований, которые до события не выполнялись, а после выполняются;
- `readiness_before`, `readiness_after`, `readiness_delta`, а также полные
  `readiness_before_details` и `readiness_after_details` формата `ReadinessResult`.

Готовность рассчитывается существующей `calculate_readiness` шага 1, с тем
же критическим весом и ограничением покрытия уровнем требования. При пустых
или нулевых требованиях оба значения и дельта равны null. Положительный
прирост навыка не гарантирует роста готовности: он может быть вне требований
или выше уже выполненного требования.

Модули допуска и симуляции шага 2 не вычисляют скоринг или ранжирование:
это следующий слой, описанный ниже. Backend Бекарыса адаптирует структуры к
прикладным моделям и отвечает за запись завершений и обновление CareerState.

## Шаг 3: публичные вызовы

Основной вызов для backend — `recommend` из `engine.py`. Он заново строит
CareerState, проверяет допуск, получает H/F, оценивает **всех** кандидатов,
сортирует их и только затем выбирает Top N:

```python
def recommend(
    employee: Mapping,
    role_profiles: Sequence,
    events: Sequence,
    history: Sequence,
    *,
    as_of: CalendarDate,
    top_n: int = 3,
    config: RecommendationConfig = DEFAULT_CONFIG,
    include_history_records: bool = False,
) -> RecommendationResult: ...

def rank_eligible_candidates(
    employee_id: str,
    candidates: Sequence,
    events: Sequence,
    history: Sequence,
    *,
    as_of: CalendarDate,
    config: RecommendationConfig = DEFAULT_CONFIG,
    include_history_records: bool = False,
) -> List[RankedRecommendation]: ...
```

`top_n` — целое число от 1 до 3, по умолчанию 3; bool недопустим. Если
кандидатов меньше, возвращаются все имеющиеся. `rank_eligible_candidates`
полезен для аудита: принимает полный допустимый пул Step 2 и возвращает
весь рейтинг, не ограничивая его тремя событиями. При его отдельном вызове
вызывающая сторона отвечает за актуальность ранее рассчитанного состояния.

```python
from backend.recommendation.engine import recommend

recommendation_result = recommend(
    employee=employee_mapping,
    role_profiles=skills_document["role_profiles"],
    events=events_document["events"],
    history=history_rows,
    as_of=skills_document["meta"]["as_of_date"],
    top_n=3,
)
```

Отдельные вычисления из `history.py` и `scoring.py`:

```python
def calculate_history_signals(
    employee_id: str,
    candidate_event: Mapping,
    events,
    history,
    *,
    as_of: CalendarDate,
    config: RecommendationConfig = DEFAULT_CONFIG,
    include_records: bool = False,
) -> HistorySignals: ...

def score_candidates(
    candidates: Sequence,
    events: Sequence,
    history_signals: Mapping,
    *,
    config: RecommendationConfig = DEFAULT_CONFIG,
) -> List[ScoredCandidate]: ...
```

`score_candidates` получает `history_signals[event_id]` с полями
`compatibility`, `feedback_signal`, `evidence`. Принимаются только допущенные
кандидаты с согласованной симуляцией; отсутствующие сигналы, повторные ID и
некорректные числовые доказательства вызывают `RecommendationInputError`.
Функция возвращает оценки в порядке `event_id`, без ранжирования.

Контракт событий `ScoringEventInput` расширяет прежний вход необязательными
`type` и `duration_hours`. `HistoryParticipationInput` добавляет
`assigned_by`, `feedback_rating`, `score`. Это минимальная граница расчёта,
не прикладные модели backend.

## Сигналы истории H и F

История используется как сигнал предпочтения, а не запрет. В неё входят
отдельные участия выбранного сотрудника, включая записи до `last_review_date`.
Идентичные повторения `record_id` учитываются один раз, конфликтующие дают
ошибку. Обязательные мероприятия по умолчанию исключены
(`config.history.include_mandatory=False`), хотя их завершения по-прежнему
могут влиять на эффективные навыки шага 1. `in_progress` и `overdue`
исключены из обоих сигналов как неокончательные/административные исходы.

Для каждой допустимой исторической записи:

```text
skill_similarity = размер пересечения developed_skill_ids / размер объединения
similarity = .60 × skill_similarity + .25 × same_type + .15 × same_format
recency = 2 ** (-age_days / 365)
weight = similarity × recency × source_weight
```

Для двух пустых наборов навыков сходство Жаккара равно 0. Отсутствующий или
пустой `type` не считается совпадением двух типов. Совпадение формата может
дать положительное сходство даже без пересечения навыков. Коэффициенты
берутся из `config.history`, а не из фиксированных значений внутри формулы.

`assigned_by` учитывается по точным значениям официального датасета:
`self=1.00`, `manager=0.50`, `hr=0.25`. Отсутствующее, неизвестное или
некорректное значение использует `unknown_source_weight=0.50` и отмечается
в доказательствах. Это умеренный вес наблюдения, а не принудительно нулевой
исход или ошибка расчёта.

`age_days` отсчитывается от явно переданного `as_of`. Для завершения с
`completed_at` используется его календарная дата; иначе — доступная дата
участия. Для самостоятельных мероприятий она может обозначать зачисление,
поэтому давность завершения также является приближением. Счётчик
`completion_date_proxy_count` отмечает использованные завершения без
фактического timestamp. Записи, у которых дата участия либо завершения позже
среза, не влияют на H/F. Системные часы не используются.

Поведенческий исход: `completed=1.00`, `dropped=0.25`, `no_show=0.00`,
`declined=0.40`. По умолчанию:

```text
H = (2 × .5 + Σ(weight × outcome)) / (2 + Σ(weight))
```

В конфигурации 2 и .5 — `prior_weight` и `neutral_value`. Без подходящей
истории H=.5; результаты ограничены диапазоном [0,1]. Отрицательная история
не удаляет кандидата из списка допустимых мероприятий.

F использует только предоставленные корректные наблюдения:

```text
rating_signal = (feedback_rating - 1) / 4
assessment_signal = score / 100
record_signal = среднее фактически присутствующих сигналов записи
F = (2 × .5 + Σ(weight × record_signal)) / (2 + Σ(weight записей с сигналом))
```

Параметры F отдельные: `feedback_prior_weight=2` и
`feedback_neutral_value=.5`. Рейтинг должен быть в [1,5], оценка — в [0,100].
Принимаются числа и числовые строки CSV. Пустые, некорректные, бесконечные
значения и bool не становятся нулевыми наблюдениями: они пропускаются и
учитываются в соответствующих счётчиках. Отзыв `dropped` учитывается на тех
же условиях. При наличии двух сигналов запись получает одно усреднённое
наблюдение с исходным весом, а не удвоенный вес.

`HistorySignals` возвращает H как `compatibility`, F как `feedback_signal`
и агрегированный `evidence`. Основные доказательства:

| Поля | Значение |
|---|---|
| `considered_history_count` | Число уникальных участий сотрудника до фильтров |
| `matched_history_count`, `effective_history_weight` | Число использованных записей с положительным весом и сумма этих весов |
| `positive_weight`, `negative_weight` | Суммы весов исходов выше/ниже нейтрального H prior; не суммы `weight × outcome` |
| `weighted_outcome_sum`, `weighted_feedback_sum` | Взвешенные суммы для воспроизведения H/F |
| `recent_similar_no_shows`, `recent_similar_completions` | Число недавних похожих записей соответствующего статуса |
| `rating_observation_count`, `assessment_observation_count`, `feedback_record_count`, `effective_feedback_weight` | Использованные оценки, записи с хотя бы одним сигналом и их вес |
| `excluded_mandatory_count`, `excluded_status_count`, `ignored_future_count` | Исключения по обязательности, исходу и дате |
| `zero_similarity_count`, `zero_weight_count`, `unknown_source_count` | Нулевое сходство/вес и источники с резервным весом |
| `missing_rating_count`, `missing_assessment_count`, `invalid_rating_count`, `invalid_assessment_count` | Пустые и некорректные значения среди записей с положительным весом |
| `completion_date_proxy_count`, `priors`, `config_snapshot` | Неопределённость давности, параметры сглаживания и использованная конфигурация |

Диагностические «недавние похожие» записи удовлетворяют
`age_days <= recent_window_days` и `similarity >= recent_similarity_threshold`,
по умолчанию 365 дней и .5. Эти пороги меняют **только счётчики**;
они не обрезают историю и не меняют H/F.

По умолчанию **детализация предпочтений по отдельным записям** не возвращается.
`include_records=True` либо `include_history_records=True` в engine добавляет
`history_signals.record_evidence` для backend/отладки: ID, статус, сходство,
давность, веса и числовые сигналы, без свободного текста отзывов. Это не
означает, что весь результат `recommend` не содержит истории: сохранённые
контракты шагов 1–2 уже возвращают ID/изменения реконструкции в
`career_state.skills_reconstruction` и ID участий в `evidence.history`.
Адаптер Бекарыса должен выбирать поля, необходимые конкретному экрану,
а не автоматически передавать весь внутренний результат во frontend.

## Семь факторов и исходные доказательства

Имена факторов совпадают с полями `config.scoring_weights`:

| Обозначение | Ключ `factors` | Вес | Исходное значение и нормализация |
|---|---|---:|---|
| C | `critical_skill_impact` | .35 | Сокращение критического дефицита / максимум среди всех кандидатов |
| G | `gap_reduction` | .25 | Сокращение общего дефицита / максимум среди всех кандидатов |
| R | `career_relevance` | .15 | Полезный целевой прирост / сумма положительных фактических приростов |
| H | `historical_compatibility` | .10 | Сглаженный `compatibility`, без нормализации по кандидатам |
| F | `history_feedback_signal` | .05 | Сглаженный `feedback_signal`, без нормализации по кандидатам |
| E | `effort_efficiency` | .05 | Полезный прирост в час / максимум среди всех кандидатов |
| A | `availability` | .05 | 1 для self_paced; иначе `1 / (1 + days_until_next_session / 30)` |

```text
score = .35C + .25G + .15R + .10H + .05F + .05E + .05A
```

Для C/G/E нулевой максимум даёт нулевой фактор. Вес C не перераспределяется,
если никто не уменьшает критические дефициты. Для R:

```text
useful_destination_gain = Σ(useful_gain по целевым навыкам)
advertised_positive_gain = Σ(положительных actual_gain из симуляции)
R = useful_destination_gain / advertised_positive_gain
```

Несмотря на имя поля `advertised_positive_gain`, в знаменателе находятся
**фактические приросты после max_level**, согласно уточнённой формуле шага 3,
а не номинальная сумма `gain` в каталоге. Нулевой знаменатель даёт R=0.
Прирост посторонних навыков и превышение целевого требования увеличивают
знаменатель без увеличения полезного числителя. R ограничивается [0,1].

Длительность для E должна быть конечным положительным числом; числовые строки
допустимы. Отсутствующая, нулевая, отрицательная, некорректная длительность,
bool и нечисловые значения дают `duration_hours=null`, `duration_valid=false`,
`raw_efficiency=0`, E=0. Так же обрабатывается крайне малая длительность,
при которой деление даёт непредставимую бесконечную эффективность. Это не
исключает кандидата. При равенстве предыдущих критериев сортировки
неизвестная длительность идёт после любой корректной длительности.

A использует доказательства доступности шага 2 и масштаб
`config.availability_wait_scale_days=30`. Некорректная структура доступности
у якобы допущенного кандидата вызывает ошибку, а не выдуманную дату.

Каждый фактор возвращает `raw`, `normalized`, `weight`, `contribution`.
Для C/G/E `raw` — количество уровней или прирост в час; для R/H/F/A это уже
отношение/сигнал [0,1]. `contribution = normalized × weight`, итог вычисляется
через `math.fsum` без округления. Округление допускается только при показе.

`scoring_evidence` сохраняет `useful_destination_gain`,
`advertised_positive_gain`, `duration_hours`, `duration_valid`,
`raw_efficiency`, `availability_wait_days`, `normalization_candidate_count`
и `normalization_maxima` с ключами `critical_skill_impact`, `gap_reduction`,
`effort_efficiency`. Полные исходные дефициты, закрытые требования,
изменения навыков и готовности остаются в `simulation` рекомендации;
роль допуска и доступность — в `evidence`.

Нормализация выполняется по **всем допустимым кандидатам до Top N**.
Изменение `top_n=1` на `top_n=3` не меняет оценки или порядок общих кандидатов.
Порядок входных событий и истории также не меняет результат. Оценка является
относительным приоритетом внутри каталога сотрудника, а не вероятностью успеха
или универсальной метрикой для сравнения сотрудников; изменение самого
допустимого пула может изменить нормализованные оценки.

## Порядок и итоговый результат

Сортировка последовательна:

1. Неокруглённый `score` по убыванию.
2. `critical_gap_reduction` по убыванию.
3. `total_gap_reduction` по убыванию.
4. Меньшее ожидание доступности; self_paced имеет ожидание 0.
5. Меньшая корректная длительность; неизвестная — последней при остальных равных.
6. `event_id` по возрастанию.

`rank` начинается с 1. Итоговый `RecommendationResult` содержит
`employee_id`, `as_of`, `status`, `target`, `career_readiness`, `skill_gaps`,
полный `career_state`, `candidate_count`, `recommendation_count`,
`recommendations` и `blocked_summary`. Число кандидатов относится ко всему
допустимому пулу, число рекомендаций — к выбранному Top N.

Каждая `RankedRecommendation` содержит `rank`, `event_id`, `title`, `score`,
`factors`, `scoring_evidence`, полную независимую `simulation`, прежние
доказательства допуска `evidence` и `history_signals`. Например, готовность
до/после читается из `simulation.readiness_before/readiness_after`, причина
ролевого допуска — из `evidence.audience_match`. Результат вызова не изменяет
входные словари и не записывает новые уровни навыков в хранилище.

## Отсутствие подходящих рекомендаций

Для сотрудника с незакрытыми требованиями и нулём кандидатов возвращается
`status="no_eligible_recommendations"`, пустой `recommendations` и
структурированный `blocked_summary`. `no_next_grade` для Lead/null остаётся
отдельным состоянием, как и `target_satisfied` или
`invalid_target_requirements` из шага 1. Без кандидатов диагностика доступна
при любом из этих состояний; при наличии кандидатов `blocked_summary=null`.

Диагностика содержит:

- `rejection_counts` — число событий для каждого кода; одно событие может
  увеличить несколько счётчиков;
- `event_rejections` — `event_id` и все `rejection_codes` каждого отказа;
- `useful_blocked_events` — добровольные события с потенциальным положительным
  влиянием, причины блокировки и сокращения общего/критического дефицита;
- `uncovered_target_gaps` — целевые дефициты, для которых ни одно добровольное
  событие каталога не даёт положительного полезного прироста из текущих навыков.

Последняя проверка **игнорирует ограничения допуска**: роль, грейд,
предварительные требования, прошлые завершения и доступность. Она показывает
наличие хотя бы какого-то потенциального прироста из текущего состояния,
а не возможность полностью закрыть требование или построить всю карьерную
траекторию. Поэтому навык может отсутствовать в `uncovered_target_gaps`, хотя
полезное мероприятие сейчас заблокировано или его предел ниже требования.
Диагностика не ослабляет правила допуска и не добавляет искусственные рекомендации.

Шаг 3 остаётся обычным Python-кодом со стандартной библиотекой. HTTP,
FastAPI, загрузка/хранение данных, API завершений, frontend и LLM-пояснения
в этот пакет не добавлены.

## Проверка

Из корня репозитория:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/recommendation -v
```

Тесты используют unittest и стандартную библиотеку. Интеграционные проверки
обрабатывают официальный датасет и независимые профили с новыми ролями,
идентификаторами и навыками. Примеры полного результата пяти типов профилей
сохранены в step1-results.json. Загрузчик в тестах служит только проверкам;
производственная загрузка остаётся в backend Бекарыса.
