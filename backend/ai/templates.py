"""Localized, deterministic renderings of validated recommendation facts.

The controller supplies validated fact values and chooses a supported language.
Catalog identifiers, role names and grades are preserved verbatim. Variants
change phrasing only; neither variant adds decisions or unsupported causality.
"""

from collections.abc import Mapping

from .config import SUPPORTED_LANGUAGES as LANGUAGES, WORDING_VARIANTS as VARIANTS


CODES = (
    "target", "impact", "skill", "readiness", "closures",
    "audience_current", "audience_target", "audience_both",
    "availability_self_paced", "availability_scheduled", "usefulness",
    "history_cold", "history_observed", "feedback", "estimate", "readiness_note",
    "status_ok", "status_no_eligible_recommendations", "status_no_next_grade",
    "status_target_satisfied", "status_invalid_target_requirements",
    "blocked_reason", "uncovered_gap",
)
REJECTION_CODES = (
    "MANDATORY", "ROLE_MISMATCH", "GRADE_MISMATCH", "PREREQUISITE_NOT_MET",
    "ALREADY_COMPLETED", "ALREADY_IN_PROGRESS", "NO_TARGET_GAP_IMPACT",
    "NO_UPCOMING_SESSION", "NO_CAREER_TARGET",
)

_REASONS = {
    "en": {
        "MANDATORY": "mandatory activity",
        "ROLE_MISMATCH": "neither the current nor explicit target role matches the audience",
        "GRADE_MISMATCH": "attained current grade does not match the audience",
        "PREREQUISITE_NOT_MET": "at least one prerequisite is unmet",
        "ALREADY_COMPLETED": "nonrecurring voluntary activity already completed",
        "ALREADY_IN_PROGRESS": "a participation is already in progress",
        "NO_TARGET_GAP_IMPACT": "no reduction of target gaps after skill caps",
        "NO_UPCOMING_SESSION": "no session on or after the snapshot date",
        "NO_CAREER_TARGET": "no resolved career target",
    },
    "ru": {
        "MANDATORY": "обязательное мероприятие",
        "ROLE_MISMATCH": "аудитории не соответствует ни текущая, ни явная целевая роль",
        "GRADE_MISMATCH": "текущий достигнутый грейд не соответствует аудитории",
        "PREREQUISITE_NOT_MET": "не выполнено хотя бы одно предварительное требование",
        "ALREADY_COMPLETED": "неповторяемое добровольное мероприятие уже завершено",
        "ALREADY_IN_PROGRESS": "есть участие со статусом «в процессе»",
        "NO_TARGET_GAP_IMPACT": "после ограничений навыков целевые дефициты не сокращаются",
        "NO_UPCOMING_SESSION": "нет сессии на дату среза или позже",
        "NO_CAREER_TARGET": "карьерная цель не определена",
    },
    "kk": {
        "MANDATORY": "міндетті іс-шара",
        "ROLE_MISMATCH": "аудиторияға қазіргі рөл де, нақты қойылған мақсаттағы рөл де сәйкес емес",
        "GRADE_MISMATCH": "қазіргі қол жеткізген грейд аудиторияға сәйкес емес",
        "PREREQUISITE_NOT_MET": "кемінде бір алдын ала талап орындалмаған",
        "ALREADY_COMPLETED": "қайталанбайтын ерікті іс-шара аяқталған",
        "ALREADY_IN_PROGRESS": "іс-шараға қатысу әлі жалғасып жатыр",
        "NO_TARGET_GAP_IMPACT": "дағды шектерін ескергенде мақсат талаптарына қатысты тапшылық азаймайды",
        "NO_UPCOMING_SESSION": "есептік күнге немесе одан кейінгі күнге сессия жоқ",
        "NO_CAREER_TARGET": "мансаптық мақсат анықталмаған",
    },
}

# Each pair contains (direct, coaching); placeholders carry the same facts.
_TEMPLATES = {
    "en": {
        "target": (
            "Target: role «{role}», grade «{grade}».",
            "Use role «{role}» at grade «{grade}» as the target for this plan.",
        ),
        "impact": (
            "Simulated completion reduces total target gaps by {total} skill levels, including {critical} critical levels.",
            "Compare the modeled benefit: {total} skill levels of target-gap reduction, including {critical} critical levels.",
        ),
        "skill": (
            "In the simulation, «{skill_id}»: {before} → {after}; required: {required}; gap: {gap_before} → {gap_after}. This skill is {critical_label}.",
            "Review the simulated change in «{skill_id}» from {before} to {after}, against a requirement of {required}; the gap changes from {gap_before} to {gap_after}. This skill is {critical_label}.",
        ),
        "readiness": (
            "Modeled target-requirement coverage: {before_pct}% → {after_pct}%; change: {delta_pp} percentage points.",
            "Compare modeled target-requirement coverage before and after: {before_pct}% → {after_pct}%, a change of {delta_pp} percentage points.",
        ),
        "closures": (
            "The simulation fully closes {total} previously unmet requirements, including {critical} critical requirements.",
            "Check the modeled closures: {total} previously unmet requirements become satisfied, including {critical} critical requirements.",
        ),
        "audience_current": (
            "The audience matches the current role «{current_role}» and attained grade «{attained_grade}».",
            "For audience eligibility, use the matching current role «{current_role}» and attained grade «{attained_grade}».",
        ),
        "audience_target": (
            "Current role: «{current_role}». The audience matches the explicit target role «{target_role}» under the application's transition policy; admission uses the attained grade «{attained_grade}».",
            "For the transition from «{current_role}» to «{target_role}», audience eligibility comes from the explicit target role under the application's policy. The admission grade remains the attained «{attained_grade}».",
        ),
        "audience_both": (
            "The audience matches both the current role «{current_role}» and explicit target role «{target_role}»; admission uses the attained grade «{attained_grade}». Target-role admission is an application policy.",
            "Both role checks match: current «{current_role}» and explicit target «{target_role}». Use attained grade «{attained_grade}» for admission; target-role admission follows the application's policy.",
        ),
        "availability_self_paced": (
            "Self-paced: available without waiting for a scheduled session.",
            "This self-paced activity can be considered without a scheduled-session wait.",
        ),
        "availability_scheduled": (
            "Next available session: {date}; wait from the snapshot date: {days} days.",
            "Plan around the next available session on {date}, {days} days after the snapshot date.",
        ),
        "usefulness": (
            "Of {actual} actual skill levels gained in the simulation after caps, {useful} reduce destination requirement gaps.",
            "Compare useful gain with all simulated gain after caps: {useful} levels reduce destination gaps out of {actual} actual levels gained.",
        ),
        "history_cold": (
            "No usable compatibility observations are available; the smoothed neutral history signal is {compatibility_fmt}.",
            "Use the neutral smoothed history signal {compatibility_fmt}: there are no usable compatibility observations.",
        ),
        "history_observed": (
            "History uses {count} participations similar by skills, type or format; compatibility signal: {compatibility_fmt}. In the last {recent_days} days at similarity ≥ {similarity_fmt}: {no_shows} no-shows and {completions} completions.",
            "Review {count} participations matched by skills, type or format, giving a compatibility signal of {compatibility_fmt}. The last {recent_days} days with similarity ≥ {similarity_fmt} contain {no_shows} no-shows and {completions} completions.",
        ),
        "feedback": (
            "Supplied observations used: {ratings} activity ratings and {assessments} final assessments. Smoothed feedback signal: {signal_fmt}.",
            "Read the smoothed feedback signal {signal_fmt} alongside its supplied observations: {ratings} activity ratings and {assessments} final assessments.",
        ),
        "estimate": (
            "Effective skills are an estimate because completion timing in the history is uncertain.",
            "Treat effective skills as an estimate: the history leaves completion timing uncertain.",
        ),
        "readiness_note": (
            "Readiness measures target-requirement coverage; it does not guarantee promotion.",
            "Interpret readiness as coverage of target requirements, without a promotion guarantee.",
        ),
        "status_ok": (
            "Selected {count} recommendations from {candidates} eligible activities.",
            "Consider these {count} recommendations from a pool of {candidates} eligible activities.",
        ),
        "status_no_eligible_recommendations": (
            "No eligible development activity is currently available for this target.",
            "Review the constraints for this target: no development activity is currently eligible.",
        ),
        "status_no_next_grade": (
            "No explicit career target is set, and the current grade has no next grade.",
            "An explicit career target is not set; the current grade has no next grade to infer.",
        ),
        "status_target_satisfied": (
            "Reconstructed effective skills cover all target-profile requirements.",
            "The reconstructed effective skills already cover every requirement of the target profile.",
        ),
        "status_invalid_target_requirements": (
            "The target profile has no positive-level requirements, so a readiness percentage cannot be calculated.",
            "Check the target profile: without positive-level requirements, its readiness percentage is unavailable.",
        ),
        "blocked_reason": (
            "Activities rejected for «{reason_label}»: {count}.",
            "Review this rejection reason, «{reason_label}», affecting {count} activities.",
        ),
        "uncovered_gap": (
            "«{skill_id}»: current {current}, required {required}, gap {gap}. No voluntary catalog activity gives a useful gain in this skill from the current state, even ignoring admission rules.",
            "Review the uncovered gap for «{skill_id}»: current {current}, required {required}, gap {gap}. Even ignoring admission rules, the voluntary catalog gives no useful gain in this skill from the current state.",
        ),
    },
    "ru": {
        "target": (
            "Цель: роль «{role}», грейд «{grade}».",
            "Ориентир для плана: роль «{role}» и грейд «{grade}».",
        ),
        "impact": (
            "Сокращение целевых дефицитов в симуляции, в уровнях навыков: всего {total}, по критическим навыкам — {critical}.",
            "Сравните модельное сокращение целевых дефицитов: всего уровней навыков — {total}, по критическим навыкам — {critical}.",
        ),
        "skill": (
            "В симуляции «{skill_id}»: {before} → {after}; требуется: {required}; дефицит: {gap_before} → {gap_after}. Это {critical_label}.",
            "Рассмотрите модельное изменение «{skill_id}»: с {before} до {after} при требовании {required}; дефицит меняется с {gap_before} до {gap_after}. Это {critical_label}.",
        ),
        "readiness": (
            "Покрытие требований цели по модели: {before_pct}% → {after_pct}%; изменение: {delta_pp} процентного пункта.",
            "Сравните покрытие требований цели до и после по модели: {before_pct}% → {after_pct}%, изменение — {delta_pp} процентного пункта.",
        ),
        "closures": (
            "В симуляции полностью закрываются ранее невыполненные требования: всего {total}, из них критических — {critical}.",
            "Проверьте модельный результат: закрытых ранее невыполненных требований — {total}, из них критических — {critical}.",
        ),
        "audience_current": (
            "Аудитория соответствует текущей роли «{current_role}» и достигнутому грейду «{attained_grade}».",
            "Для допуска по аудитории учитываются совпадающие текущая роль «{current_role}» и достигнутый грейд «{attained_grade}».",
        ),
        "audience_target": (
            "Текущая роль: «{current_role}». Аудитория совпала с явной целевой ролью «{target_role}» по политике переходов приложения; для допуска используется достигнутый грейд «{attained_grade}».",
            "Для перехода из «{current_role}» в «{target_role}» допуск по аудитории основан на явной целевой роли согласно политике приложения. Грейд допуска остаётся достигнутым: «{attained_grade}».",
        ),
        "audience_both": (
            "Аудитория совпала с текущей ролью «{current_role}» и явной целевой ролью «{target_role}»; грейд допуска — достигнутый «{attained_grade}». Допуск через целевую роль является политикой приложения.",
            "Совпали обе проверки роли: текущая «{current_role}» и явная целевая «{target_role}». Для допуска учитывается достигнутый грейд «{attained_grade}»; использование целевой роли предусмотрено политикой приложения.",
        ),
        "availability_self_paced": (
            "Самостоятельное обучение доступно без ожидания сессии по расписанию.",
            "Для самостоятельного обучения не требуется ждать сессию по расписанию.",
        ),
        "availability_scheduled": (
            "Ближайшая доступная сессия: {date}; ожидание от даты среза: {days} дн.",
            "Ориентируйтесь на ближайшую доступную сессию {date}, через {days} дн. после даты среза.",
        ),
        "usefulness": (
            "Фактический прирост навыков в симуляции после ограничений, в уровнях: всего {actual}, на сокращение целевых дефицитов приходится {useful}.",
            "Сравните прирост по модели после ограничений, в уровнях навыков: на сокращение целевых дефицитов приходится {useful}, весь фактический прирост — {actual}.",
        ),
        "history_cold": (
            "Учитываемых наблюдений для оценки совместимости нет; нейтральный сглаженный сигнал истории — {compatibility_fmt}.",
            "Используется нейтральный сглаженный сигнал истории {compatibility_fmt}: учитываемых наблюдений для оценки совместимости нет.",
        ),
        "history_observed": (
            "Учтено участий, схожих по навыкам, типу или формату: {count}; сигнал совместимости — {compatibility_fmt}. За последние {recent_days} дней при сходстве ≥ {similarity_fmt}: неявок {no_shows}, завершений {completions}.",
            "Рассмотрите историю по сходным навыкам, типу или формату: число участий — {count}; сигнал совместимости — {compatibility_fmt}. За последние {recent_days} дней со сходством ≥ {similarity_fmt} учтено неявок {no_shows} и завершений {completions}.",
        ),
        "feedback": (
            "Использовано предоставленных оценок мероприятия: {ratings}; итоговых оценок обучения: {assessments}. Сглаженный сигнал обратной связи — {signal_fmt}.",
            "Рассматривайте сглаженный сигнал обратной связи {signal_fmt} вместе с наблюдениями: оценок мероприятия {ratings}, итоговых оценок обучения {assessments}.",
        ),
        "estimate": (
            "Эффективные навыки восстановлены приблизительно: в истории есть неопределённость времени завершения.",
            "Учитывайте приблизительность эффективных навыков: история не позволяет однозначно определить время завершения.",
        ),
        "readiness_note": (
            "Готовность измеряет покрытие требований цели и не гарантирует повышение.",
            "Воспринимайте готовность как покрытие требований цели, без гарантии повышения.",
        ),
        "status_ok": (
            "Выбрано рекомендаций: {count}; всего допустимых мероприятий: {candidates}.",
            "Рассмотрите выбранные рекомендации: их {count}, всего допустимых мероприятий — {candidates}.",
        ),
        "status_no_eligible_recommendations": (
            "Сейчас для этой цели нет подходящего мероприятия, прошедшего все условия допуска.",
            "Рассмотрите ограничения для этой цели: сейчас ни одно мероприятие не проходит все условия допуска.",
        ),
        "status_no_next_grade": (
            "Явная карьерная цель не задана, а у текущего грейда нет следующего.",
            "Для текущего грейда нельзя определить следующий: его нет, и явная карьерная цель не задана.",
        ),
        "status_target_satisfied": (
            "Восстановленные эффективные навыки покрывают все требования целевого профиля.",
            "Все требования целевого профиля уже покрываются восстановленными эффективными навыками.",
        ),
        "status_invalid_target_requirements": (
            "У целевого профиля нет требований с положительными уровнями, поэтому процент готовности рассчитать нельзя.",
            "Проверьте целевой профиль: без требований с положительными уровнями процент готовности недоступен.",
        ),
        "blocked_reason": (
            "Мероприятий с причиной отказа «{reason_label}»: {count}.",
            "Рассмотрите причину отказа «{reason_label}»; затронуто мероприятий: {count}.",
        ),
        "uncovered_gap": (
            "«{skill_id}»: текущий уровень {current}, требуется {required}, дефицит {gap}. Ни одно добровольное мероприятие каталога не даёт полезного прироста этого навыка из текущего состояния, даже без учёта условий допуска.",
            "Рассмотрите непокрытый дефицит «{skill_id}»: текущий уровень {current}, требуется {required}, дефицит {gap}. Даже без учёта условий допуска добровольный каталог не даёт полезного прироста этого навыка из текущего состояния.",
        ),
    },
    "kk": {
        "target": (
            "Мақсат: «{role}» рөлі, «{grade}» грейді.",
            "Осы жоспардың бағдары — «{role}» рөлі және «{grade}» грейді.",
        ),
        "impact": (
            "Симуляция бойынша аяқтау мақсат талаптарына қатысты дағды тапшылығын {total} деңгейге азайтады, оның {critical} деңгейі критикалық дағдыларға қатысты.",
            "Модельдегі әсерді салыстырыңыз: мақсат талаптарына қатысты дағды тапшылығы {total} деңгейге азаяды, оның {critical} деңгейі критикалық дағдыларға қатысты.",
        ),
        "skill": (
            "Симуляцияда «{skill_id}»: {before} → {after}; талап етілетін деңгей: {required}; тапшылық: {gap_before} → {gap_after}. Бұл — {critical_label}.",
            "«{skill_id}» дағдысының модельдегі өзгерісін қараңыз: {before} деңгейінен {after} деңгейіне, талап — {required}; тапшылық {gap_before} деңгейінен {gap_after} деңгейіне өзгереді. Бұл — {critical_label}.",
        ),
        "readiness": (
            "Модель бойынша мақсат талаптарының қамтылуы: {before_pct}% → {after_pct}%; өзгеріс: {delta_pp} пайыздық тармақ.",
            "Модель бойынша мақсат талаптарының бұрынғы және кейінгі қамтылуын салыстырыңыз: {before_pct}% → {after_pct}%, өзгеріс — {delta_pp} пайыздық тармақ.",
        ),
        "closures": (
            "Симуляцияда бұрын орындалмаған {total} талап толық орындалады, оның ішінде {critical} критикалық талап бар.",
            "Модель нәтижесін тексеріңіз: бұрын орындалмаған {total} талап орындалады, соның {critical} талабы критикалық.",
        ),
        "audience_current": (
            "Аудитория қазіргі «{current_role}» рөліне және қол жеткізген «{attained_grade}» грейдіне сәйкес.",
            "Аудитория бойынша қатысуға рұқсат үшін сәйкес келетін қазіргі «{current_role}» рөлі мен қол жеткізген «{attained_grade}» грейді ескеріледі.",
        ),
        "audience_target": (
            "Қазіргі рөл: «{current_role}». Аудитория нақты қойылған мақсаттағы «{target_role}» рөліне қолданбаның ауысу саясаты бойынша сәйкес келеді; қатысуға рұқсат үшін қол жеткізген «{attained_grade}» грейді қолданылады.",
            "«{current_role}» рөлінен «{target_role}» рөліне ауысу кезінде аудитория бойынша рұқсат қолданба саясатына сай нақты мақсаттағы рөлге негізделеді. Қатысуға рұқсат грейді — қол жеткізген «{attained_grade}» грейді.",
        ),
        "audience_both": (
            "Аудитория қазіргі «{current_role}» рөліне де, нақты мақсаттағы «{target_role}» рөліне де сәйкес; қатысуға рұқсат үшін қол жеткізген «{attained_grade}» грейді қолданылады. Мақсаттағы рөл арқылы қатысу — қолданба саясаты.",
            "Екі рөл де аудиторияға сәйкес: қазіргі «{current_role}» және нақты мақсаттағы «{target_role}». Қатысуға рұқсатта қол жеткізген «{attained_grade}» грейді ескеріледі; мақсаттағы рөлді пайдалану қолданба саясатында қарастырылған.",
        ),
        "availability_self_paced": (
            "Өз бетімен оқуды кестедегі сессияны күтпей бастауға болады.",
            "Өз бетімен оқу үшін кестедегі сессияны күту қажет емес.",
        ),
        "availability_scheduled": (
            "Келесі қолжетімді сессия: {date}; есептік күннен бастап күту мерзімі: {days} күн.",
            "Есептік күннен кейін {days} күн өткенде, {date} күні болатын келесі қолжетімді сессияны ескеріңіз.",
        ),
        "usefulness": (
            "Симуляцияда шектерді ескергеннен кейін дағдылардың нақты өсімі — {actual} деңгей. Оның {useful} деңгейі мақсат талаптарына қатысты тапшылықты азайтады.",
            "Модельдегі шектерді ескергеннен кейінгі өсімді салыстырыңыз: жалпы өсім — {actual} деңгей, мақсат талаптарына қатысты тапшылықты азайтатын бөлігі — {useful} деңгей.",
        ),
        "history_cold": (
            "Үйлесімділікті бағалауға жарамды бақылаулар жоқ; тарихтың бейтарап тегістелген сигналы — {compatibility_fmt}.",
            "Үйлесімділікті бағалауға жарамды бақылаулар болмағандықтан, тарихтың {compatibility_fmt} бейтарап тегістелген сигналы қолданылады.",
        ),
        "history_observed": (
            "Дағдылары, түрі немесе форматы ұқсас {count} қатысу ескерілді; үйлесімділік сигналы — {compatibility_fmt}. Соңғы {recent_days} күнде ұқсастығы ≥ {similarity_fmt} болғандар: келмеу — {no_shows}, аяқтау — {completions}.",
            "Дағдылар, түр немесе формат бойынша салыстырылған {count} қатысуды қараңыз; үйлесімділік сигналы — {compatibility_fmt}. Соңғы {recent_days} күнде ұқсастығы ≥ {similarity_fmt} болған қатысуларда {no_shows} келмеу және {completions} аяқтау тіркелген.",
        ),
        "feedback": (
            "Ескерілген іс-шара бағаларының саны: {ratings}; қорытынды оқу бағаларының саны: {assessments}. Кері байланыстың тегістелген сигналы — {signal_fmt}.",
            "Кері байланыстың {signal_fmt} тегістелген сигналын бақылаулармен бірге қараңыз: іс-шара бағалары — {ratings}, қорытынды оқу бағалары — {assessments}.",
        ),
        "estimate": (
            "Тиімді дағды деңгейлері шамамен қалпына келтірілген: тарихта аяқталу уақытына қатысты белгісіздік бар.",
            "Тиімді дағды деңгейлерінің шамамен есептелгенін ескеріңіз: тарих аяқталу уақытын бірмәнді анықтауға мүмкіндік бермейді.",
        ),
        "readiness_note": (
            "Дайындық көрсеткіші мақсат талаптарының қамтылуын өлшейді және қызметте жоғарылауға кепілдік бермейді.",
            "Дайындықты мақсат талаптарының қамтылуы ретінде түсініңіз; ол қызметте жоғарылауға кепілдік емес.",
        ),
        "status_ok": (
            "Талаптарға сай {candidates} іс-шараның ішінен {count} ұсыныс таңдалды.",
            "Талаптарға сай {candidates} іс-шарадан таңдалған {count} ұсынысты қарастырыңыз.",
        ),
        "status_no_eligible_recommendations": (
            "Қазір осы мақсат үшін қатысудың барлық шартына сай келетін даму іс-шарасы жоқ.",
            "Осы мақсатқа қатысты шектеулерді қараңыз: қазір ешбір іс-шара қатысудың барлық шартына сай келмейді.",
        ),
        "status_no_next_grade": (
            "Нақты мансаптық мақсат қойылмаған және қазіргі грейдтен кейінгі грейд жоқ.",
            "Қазіргі грейдтен кейінгі грейдті анықтау мүмкін емес: ондай грейд жоқ, ал нақты мансаптық мақсат қойылмаған.",
        ),
        "status_target_satisfied": (
            "Қалпына келтірілген тиімді дағдылар мақсатты профильдің барлық талабын қамтиды.",
            "Мақсатты профильдің барлық талабы қалпына келтірілген тиімді дағдылармен қамтылған.",
        ),
        "status_invalid_target_requirements": (
            "Мақсатты профильде деңгейі нөлден жоғары талаптар жоқ, сондықтан дайындық пайызын есептеу мүмкін емес.",
            "Мақсатты профильді тексеріңіз: деңгейі нөлден жоғары талаптар болмаса, дайындық пайызы есептелмейді.",
        ),
        "blocked_reason": (
            "«{reason_label}» себебімен қабылданбаған іс-шара саны: {count}.",
            "«{reason_label}» қабылдамау себебін қараңыз; оған қатысты іс-шара саны: {count}.",
        ),
        "uncovered_gap": (
            "«{skill_id}»: қазіргі деңгей {current}, талап {required}, тапшылық {gap}. Қатысу шарттарын ескермегеннің өзінде, каталогтағы ешбір ерікті іс-шара бұл дағдыға қазіргі күйден пайдалы өсім бермейді.",
            "«{skill_id}» бойынша қамтылмаған тапшылықты қараңыз: қазіргі деңгей {current}, талап {required}, тапшылық {gap}. Тіпті қатысу шарттарын ескермесе де, ерікті іс-шаралар каталогы бұл дағдыға қазіргі күйден пайдалы өсім бермейді.",
        ),
    },
}

_CRITICAL_LABELS = {
    "en": {True: "critical for the target", False: "noncritical for the target"},
    "ru": {True: "критический навык для цели", False: "некритический навык для цели"},
    "kk": {True: "мақсат үшін критикалық дағды", False: "мақсат үшін критикалық емес дағды"},
}


def render_fact(code, values, language, variant="direct") -> str:
    """Render a validated fact without changing identifiers or its values.

    Percentages use two decimal places, percentage-point change has an explicit
    sign, and history signals use three decimal places. A dot is used for decimal
    notation consistently across languages. Language fallback belongs to callers.
    """
    if language not in LANGUAGES:
        raise ValueError("Unsupported explanation language")
    if variant not in VARIANTS:
        raise ValueError("Unsupported explanation variant")
    if code not in CODES:
        raise ValueError("Unsupported explanation fact code")
    if not isinstance(values, Mapping):
        raise ValueError("Fact values must be a mapping")
    formatted = dict(values)
    if code == "skill":
        if type(values["critical"]) is not bool:
            raise ValueError("Critical flag must be boolean")
        formatted["critical_label"] = _CRITICAL_LABELS[language][values["critical"]]
    elif code == "readiness":
        formatted.update(
            before_pct="{:.2f}".format(values["before"] * 100),
            after_pct="{:.2f}".format(values["after"] * 100),
            delta_pp="{:+.2f}".format(values["delta"] * 100),
        )
    elif code in ("history_cold", "history_observed"):
        formatted["compatibility_fmt"] = "{:.3f}".format(values["compatibility"])
        if code == "history_observed":
            formatted["similarity_fmt"] = "{:.3f}".format(values["similarity_min"])
    elif code == "feedback":
        formatted["signal_fmt"] = "{:.3f}".format(values["signal"])
    elif code == "blocked_reason":
        if values["reason_code"] not in REJECTION_CODES:
            raise ValueError("Unsupported rejection reason code")
        formatted["reason_label"] = _REASONS[language][values["reason_code"]]
    return _TEMPLATES[language][code][VARIANTS.index(variant)].format_map(formatted)
