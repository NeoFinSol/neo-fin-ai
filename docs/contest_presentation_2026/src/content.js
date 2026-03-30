const CONTACT = {
  author: "[Ваше имя]",
  email: "email@example.com",
  telegram: "@telegram",
  github: "github.com/NeoFinSol/neo-fin-ai",
};

const MAIN_STORY = [
  {
    role: "main",
    layout: "hero",
    tag: "Вступление",
    title: "NeoFin AI сокращает цену и время первичного анализа PDF-отчётности",
    subtitle: "Платформа превращает неудобный документ в управляемый финансовый результат для профессионального контура.",
    statementTitle: "Главная мысль",
    statement: "NeoFin AI автоматизирует самый дорогой и рутинный участок процесса: извлечение, первичную структуризацию и объяснимый финансовый разбор отчётности из PDF.",
    badges: [
      { text: "15 метрик", accent: "emerald" },
      { text: "13 коэффициентов", accent: "cyan", w: 2.0 },
      { text: "Скоринг 0–100", accent: "amber" },
      { text: "B2B-фокус", accent: "emerald" }
    ],
    stats: [
      { value: "PDF -> вывод", label: "ядро продукта", accent: "emerald", w: 2.4 },
      { value: "Объяснимо", label: "источник + confidence", accent: "cyan", w: 2.4 },
      { value: "В реальном времени", label: "API + WebSocket", accent: "amber", w: 2.4 },
      { value: "Повторяемо", label: "демо и история", accent: "cyan", w: 2.4 }
    ],
    sideTitle: "Почему это сильный проект",
    sideBullets: [
      "Он решает конкретную профессиональную боль, а не демонстрирует абстрактный эффект от ИИ.",
      "Числовой результат остаётся воспроизводимым даже без внешнего LLM-провайдера.",
      "Продукт уже выглядит как рабочий контур: есть runtime, API, история и сценарий демонстрации."
    ],
    bridge: "NeoFin AI не заменяет финансиста — он освобождает его от дорогого ручного подготовительного этапа."
  },
  {
    role: "main",
    layout: "split",
    tag: "Проблема 1/3",
    title: "Почему PDF-отчётность остаётся узким горлышком",
    subtitle: "Формулы известны давно. Дорогой участок находится раньше — на этапе извлечения и подготовки данных.",
    leftTitle: "Что ломает скорость анализа",
    leftBullets: [
      "Отчётность приходит в формате, удобном для чтения человеком, но неудобном для машинного разбора.",
      "Текстовые PDF, таблицы и scanned-документы требуют разных стратегий обработки.",
      "Команда тратит часы на подготовку ещё до того, как начинается финансовая интерпретация."
    ],
    rightTitle: "Где именно теряется ценность",
    rightCards: [
      { title: "Ручной перенос", body: "Числа переезжают из PDF в таблицы руками.", accent: "amber" },
      { title: "Разные макеты", body: "Каждый документ требует нового мини-разбора.", accent: "cyan" },
      { title: "Сдвиг внимания", body: "Вместо выводов команда занята технической подготовкой.", accent: "red" }
    ],
    bridge: "Задача NeoFin AI — не «как придумать новую формулу», а как быстрее и надёжнее добраться до самих чисел."
  },
  {
    role: "main",
    layout: "contrast",
    tag: "Проблема 2/3",
    title: "Ручной подготовительный этап создаёт три прямых потери",
    subtitle: "Эта боль особенно сильна там, где отчётность разбирают регулярно и время специалиста уже дорого стоит.",
    stats: [
      { value: "Время", label: "слишком много часов уходит до этапа интерпретации", accent: "cyan" },
      { value: "Ошибки", label: "механические промахи возникают из-за переноса, а не из-за логики", accent: "red" },
      { value: "Разброс", label: "разные люди и документы дают разную глубину первичного разбора", accent: "amber" }
    ],
    lowerPanels: [
      { title: "Кто чувствует боль сильнее всего", body: "Финансовые команды, аудит, консалтинг, риск-подразделения банков и средний бизнес с регулярным потоком PDF-отчётности.", accent: "emerald" },
      { title: "Что это значит экономически", body: "Компания платит не только за экспертизу, но и за рутину, которую можно и нужно автоматизировать.", accent: "cyan" }
    ],
    bridge: "NeoFin AI монетизирует именно это узкое место — между документом и готовым аналитическим действием."
  },
  {
    role: "main",
    layout: "contrast",
    tag: "Проблема 3/3",
    title: "Почему рынок готов к такому решению именно сейчас",
    subtitle: "Спрос формируют не только технологии, но и изменение требований к самой финансовой функции.",
    stats: [
      { value: "Быстрее", label: "решения требуют более короткого аналитического цикла", accent: "emerald" },
      { value: "Прозрачнее", label: "результат должен быть объясним и прослеживаем", accent: "cyan" },
      { value: "Гибче", label: "бизнесу нужны и облачные, и закрытые сценарии", accent: "amber" }
    ],
    lowerPanels: [
      { title: "Сдвиг ожиданий", body: "Компании всё меньше готовы оплачивать ручную механику там, где её можно заменить управляемым инструментом.", accent: "cyan" },
      { title: "Окно возможности", body: "NeoFin AI попадает ровно в точку пересечения document AI, explainability и профессионального B2B-процесса.", accent: "emerald" }
    ]
  },
  {
    role: "main",
    layout: "hero",
    tag: "Продукт 1/3",
    title: "NeoFin AI берёт на себя весь путь от PDF до структурированного финансового результата",
    subtitle: "Один продуктовый контур вместо набора ручных шагов и временных таблиц.",
    statementTitle: "Что делает продукт",
    statement: "Платформа принимает PDF, извлекает ключевые показатели из текста, таблиц и OCR-контура, рассчитывает коэффициенты и скоринг, а затем добавляет объяснимую интерпретацию и рекомендации.",
    badges: [
      { text: "Загрузка -> обработка", accent: "cyan", w: 2.35 },
      { text: "Метрики + коэффициенты", accent: "emerald", w: 2.55 },
      { text: "Скоринг + NLP", accent: "amber", w: 2.0 }
    ],
    stats: [
      { value: "01", label: "загрузка и task_id", accent: "cyan" },
      { value: "02", label: "извлечение и confidence", accent: "emerald" },
      { value: "03", label: "score и уровень риска", accent: "amber" },
      { value: "04", label: "AI-комментарии", accent: "cyan" }
    ],
    sideTitle: "Почему это важно",
    sideBullets: [
      "Пользователь получает не голый документ, а готовый аналитический объект.",
      "Сценарий работает и для UI, и для API, и для многопериодного сравнения.",
      "Продукт ускоряет переход от файла к обсуждению решения."
    ]
  },
  {
    role: "main",
    layout: "contrast",
    tag: "Продукт 2/3",
    title: "На выходе пользователь видит не хаос, а понятную структуру результата",
    subtitle: "Это делает продукт пригодным для действия, а не только для демонстрации технологии.",
    stats: [
      { value: "15", label: "финансовых метрик", accent: "emerald" },
      { value: "13", label: "коэффициентов", accent: "cyan" },
      { value: "0–100", label: "интегральный скоринг", accent: "amber" },
      { value: "4", label: "слоя результата: data, score, NLP, traceability", accent: "cyan", w: 2.8 }
    ],
    lowerPanels: [
      { title: "Что входит в результат", body: "Метрики, коэффициенты, score, risk_level, confidence_score, factors, normalized scores, NLP-рекомендации и extraction metadata.", accent: "emerald" },
      { title: "Что это даёт команде", body: "Можно сразу обсуждать качество бизнеса, а не спорить о том, откуда брать числа и насколько им верить.", accent: "cyan" }
    ]
  },
  {
    role: "main",
    layout: "split",
    tag: "Продукт 3/3",
    title: "Главный moat продукта — объяснимость, а не просто извлечение чисел",
    subtitle: "NeoFin AI показывает, почему результату можно доверять и где его стоит перепроверить.",
    leftTitle: "Что видит пользователь",
    leftBullets: [
      "Для каждого показателя сохраняются source и confidence.",
      "Низконадёжные значения могут оставаться видимыми, но не участвовать в расчётах.",
      "Результат объясняется языком доверия к данным, а не языком чёрного ящика."
    ],
    rightTitle: "Почему это сильнее обычного document AI",
    rightCards: [
      { title: "Не просто найдено", body: "Важно не только наличие числа, но и происхождение этого числа.", accent: "emerald" },
      { title: "Не просто автоматизация", body: "Продукт уменьшает риск тихой деградации аналитики.", accent: "cyan" },
      { title: "Не просто интерфейс", body: "Explainability делает решение пригодным для профессионального B2B-контура.", accent: "amber" }
    ],
    bridge: "Именно объяснимость переводит NeoFin AI из категории «интересный AI-инструмент» в категорию рабочего финансового продукта."
  },
  {
    role: "main",
    layout: "split",
    tag: "Доверие 1/3",
    title: "Продукт спроектирован под сложные, а не только под идеальные документы",
    subtitle: "Ценность появляется там, где у клиента неудобный PDF, скан или повреждённый текстовый слой — и всё равно нужен результат.",
    leftTitle: "Три входных контура",
    leftBullets: [
      "Текстовый PDF: быстрый доступ к текстовому слою.",
      "Таблицы: извлечение структурированных числовых блоков.",
      "Scanned PDF: OCR-путь для тяжёлых документов и сканов."
    ],
    rightTitle: "Защитные механизмы качества",
    rightCards: [
      { title: "Фильтры мусора", body: "Аномальные значения отсеиваются до аналитики.", accent: "red" },
      { title: "Confidence filter", body: "Сомнительное число не портит коэффициенты.", accent: "emerald" },
      { title: "Regression corpus", body: "Сложные кейсы закрепляются тестами, а не памятью команды.", accent: "cyan" }
    ]
  },
  {
    role: "main",
    layout: "split",
    tag: "Доверие 2/3",
    title: "Почему результат воспроизводим и управляем, а не случайно удачен",
    subtitle: "Архитектура намеренно разделяет ответственность и не смешивает API, аналитику, AI и хранение.",
    leftTitle: "Архитектурный принцип",
    leftBullets: [
      "Слои идут сверху вниз: routers -> tasks -> analysis -> ai_service -> db/crud.",
      "Числовой результат и AI-интерпретация разведены в разные уровни системы.",
      "Это упрощает тестирование, развитие и контроль качества изменений."
    ],
    rightTitle: "Что это даёт бизнесу",
    rightCards: [
      { title: "Повторяемость", body: "Одинаковый документ даёт одинаковый числовой слой.", accent: "cyan" },
      { title: "Управляемость", body: "Ошибки и статусы имеют явный жизненный цикл.", accent: "emerald" },
      { title: "Расширяемость", body: "Интеграции и новые сценарии не ломают ядро продукта.", accent: "amber" }
    ]
  },
  {
    role: "main",
    layout: "split",
    tag: "Доверие 3/3",
    title: "Как продукт встраивается в рабочий контур, а не живёт отдельно",
    subtitle: "NeoFin AI можно использовать как пользовательский сервис и как API-слой для внешних процессов.",
    leftTitle: "Интеграционный путь",
    leftBullets: [
      "Старт через POST /upload с мгновенным task_id.",
      "Статусы приходят в WebSocket в реальном времени.",
      "Результат доступен и в UI, и через API, и в истории анализов."
    ],
    rightTitle: "Что делает интеграцию зрелой",
    rightCards: [
      { title: "API key", body: "Явная модель доступа к основным endpoint-ам.", accent: "cyan" },
      { title: "Polling fallback", body: "Если WS недоступен, сценарий всё равно доходит до результата.", accent: "emerald" },
      { title: "История", body: "Запуск не исчезает после показа: к нему можно вернуться.", accent: "amber" }
    ]
  },
  {
    role: "main",
    layout: "contrast",
    tag: "Доказательство 1/2",
    title: "Проект уже подтверждён не только слайдами, но и повторяемыми demo-сценариями",
    subtitle: "Сильная часть NeoFin AI — не обещание «можно показать», а сценарий «уже воспроизводимо показывается».",
    stats: [
      { value: "text", label: "эталонный текстовый сценарий", accent: "cyan", w: 2.6 },
      { value: "scanned", label: "OCR-heavy сценарий", accent: "emerald", w: 2.6 },
      { value: "multi-period", label: "динамика по периодам", accent: "amber", w: 2.6 }
    ],
    lowerPanels: [
      { title: "Почему это важно для жюри", body: "Демонстрация опирается на manifest-driven сценарии и headline-метрики, а не только на удачный клик в интерфейсе.", accent: "emerald" },
      { title: "Что это доказывает", body: "У проекта уже есть инженерная дисциплина вокруг показа: smoke path, operator card и резервный сценарий.", accent: "cyan" }
    ]
  },
  {
    role: "main",
    layout: "split",
    tag: "Доказательство 2/2",
    title: "Почему NeoFin AI уже выглядит как рабочий контур, а не как концепт",
    subtitle: "Система умеет не только анализировать, но и стабильно проживать жизненный цикл выполнения задачи.",
    leftTitle: "Что уже есть",
    leftBullets: [
      "Два runtime-режима: background и celery.",
      "Статусы в реальном времени: extracting, scoring, analyzing, completed, cancelled, failed.",
      "Runbook и operator card для повторяемой демонстрации и репетиции."
    ],
    rightTitle: "Чем это отличается от сырого MVP",
    rightCards: [
      { title: "Не только логика", body: "Продуман и слой исполнения, а не только extraction core.", accent: "cyan" },
      { title: "Не только happy path", body: "Есть fallback, history, status lifecycle и backup-contour.", accent: "emerald" },
      { title: "Не только demo", body: "Архитектура уже совместима с пилотной эксплуатацией.", accent: "amber" }
    ]
  },
  {
    role: "main",
    layout: "contrast",
    tag: "Бизнес 1/3",
    title: "Кто платит и почему: NeoFin AI — это B2B-продукт в первую очередь",
    subtitle: "Коммерческий потенциал строится не на массовом трафике, а на регулярной профессиональной боли.",
    stats: [
      { value: "B2B", label: "основной драйвер выручки", accent: "emerald" },
      { value: "Регулярность", label: "повторяемый поток документов и сценариев", accent: "cyan", w: 2.5 },
      { value: "Экономия труда", label: "ценность легко объяснить языком времени и затрат", accent: "amber", w: 2.6 }
    ],
    lowerPanels: [
      { title: "Приоритетные сегменты", body: "Финансовый аутсорсинг, аудит, консалтинг, финслужбы среднего бизнеса, отдельные риск-команды.", accent: "emerald" },
      { title: "Почему не B2C как основа", body: "B2C полезен как дополнительная воронка, но не даёт той глубины монетизации и контрактной устойчивости, что B2B.", accent: "cyan" }
    ]
  },
  {
    role: "main",
    layout: "split",
    tag: "Бизнес 2/3",
    title: "Где первая волна клиентов и как работает модель монетизации",
    subtitle: "Стартовый сегмент выбирается по скорости сделки и лёгкости доказательства ценности, а не только по размеру рынка.",
    leftTitle: "Первая волна коммерциализации",
    leftBullets: [
      "Аутсорсинговые финансовые команды.",
      "Бухгалтерские и аудиторские практики.",
      "Небольшие и средние консалтинговые компании."
    ],
    rightTitle: "Как проект зарабатывает",
    rightCards: [
      { title: "Облачная подписка", body: "Быстрый вход, пилоты, повторяемый сервисный сценарий.", accent: "cyan" },
      { title: "Корпоративный пакет", body: "Командное использование и интеграционный контур для B2B.", accent: "emerald" },
      { title: "Частный контур", body: "Отдельная ценность для клиентов с чувствительными данными и локальным размещением.", accent: "amber" }
    ]
  },
  {
    role: "main",
    layout: "contrast",
    tag: "Бизнес 3/3",
    title: "Почему проект выглядит сильным кандидатом уже сейчас",
    subtitle: "История сходится в одну линию: боль понятна, продукт реален, демо повторяемо, коммерческий вход в рынок не надуман.",
    stats: [
      { value: "Проблема", label: "чёткая и дорогая для бизнеса", accent: "cyan" },
      { value: "Продукт", label: "объяснимый и инженерно зрелый", accent: "emerald" },
      { value: "Рост", label: "понятен путь от конкурса к пилотам", accent: "amber" }
    ],
    lowerPanels: [
      { title: "Roadmap после финала", body: "Production hardening, backup/restore, performance-pass, interactive OCR corrections, усиление корпоративного контура.", accent: "cyan" },
      { title: "Итоговый тезис", body: "NeoFin AI — это не красивая оболочка вокруг AI, а профессиональный продукт, который можно развивать в пилоты и внедрение.", accent: "emerald" }
    ]
  }
];

const BACKUP = [
  {
    role: "backup",
    layout: "reference",
    tag: "Приложение 1",
    title: "15 базовых финансовых метрик в текущем контракте продукта",
    subtitle: "Справочный deep dive для вопросов о составе извлекаемых данных.",
    columns: 3,
    sections: [
      { title: "core financials", body: "revenue\nnet_profit\ntotal_assets\nequity\nliabilities", accent: "emerald", mono: true },
      { title: "balance context", body: "current_assets\nshort_term_liabilities\naccounts_receivable\ninventory\ncash_and_equivalents", accent: "cyan", mono: true },
      { title: "extended inputs", body: "ebitda\nebit\ninterest_expense\ncost_of_goods_sold\naverage_inventory", accent: "amber", mono: true }
    ],
    bridge: "Все эти поля уже согласованы с frontend contract в interfaces.ts и используются как основа для коэффициентов и score."
  },
  {
    role: "backup",
    layout: "reference",
    tag: "Приложение 2",
    title: "13 коэффициентов по четырём аналитическим группам",
    subtitle: "Справочный слой для вопросов о глубине финансового анализа.",
    columns: 2,
    sections: [
      { title: "Ликвидность", body: "current_ratio\nquick_ratio\nabsolute_liquidity_ratio", accent: "cyan", mono: true },
      { title: "Рентабельность", body: "roa\nroe\nros\nebitda_margin", accent: "emerald", mono: true },
      { title: "Финансовая устойчивость", body: "equity_ratio\nfinancial_leverage\ninterest_coverage", accent: "amber", mono: true },
      { title: "Деловая активность", body: "asset_turnover\ninventory_turnover\nreceivables_turnover", accent: "cyan", mono: true }
    ]
  },
  {
    role: "backup",
    layout: "contrast",
    tag: "Приложение 3",
    title: "Как устроен score и риск-профиль результата",
    subtitle: "NeoFin AI выдаёт не только коэффициенты, но и управляемый слой оценки качества бизнеса.",
    stats: [
      { value: "0–100", label: "итоговый score", accent: "emerald" },
      { value: "4", label: "low / medium / high / critical", accent: "amber", w: 2.8 },
      { value: "confidence", label: "отдельный показатель полноты и надёжности данных", accent: "cyan", w: 2.8 }
    ],
    lowerPanels: [
      { title: "Что входит в score block", body: "score, risk_level, confidence_score, factors и normalized_scores.", accent: "emerald" },
      { title: "Почему это полезно", body: "Финансовая команда получает не только числа, но и более быстрый язык для обсуждения качества компании.", accent: "cyan" }
    ]
  },
  {
    role: "backup",
    layout: "contrast",
    tag: "Приложение 4",
    title: "Confidence filter — главный защитный механизм числового контура",
    subtitle: "Он не позволяет сомнительному значению незаметно исказить коэффициенты и итоговый score.",
    stats: [
      { value: "0.9", label: "table_exact", accent: "emerald" },
      { value: "0.7", label: "table_partial", accent: "cyan" },
      { value: "0.5", label: "text_regex / ocr", accent: "amber" },
      { value: "0.3", label: "derived", accent: "red" }
    ],
    lowerPanels: [
      { title: "Правило", body: "В расчёты идут показатели с confidence >= 0.5; остальные видимы, но не влияют на аналитику.", accent: "emerald" },
      { title: "Эффект", body: "Пользователь понимает, где системе можно доверять, а где документ стоит перепроверить вручную.", accent: "cyan" }
    ]
  },
  {
    role: "backup",
    layout: "code",
    tag: "Приложение 5",
    title: "Как выглядит результат анализа внутри контрактов продукта",
    subtitle: "Справочный слайд для вопросов о wire shape и масштабируемости результата.",
    sideSections: [
      { title: "AnalysisResponse", body: "status\ndata -> metrics\ndata -> ratios\ndata -> score\ndata -> nlp\ndata -> extraction_metadata", accent: "emerald", mono: true },
      { title: "MultiAnalysisResponse", body: "session_id\nstatus\nprogress\nperiods[]", accent: "cyan", mono: true }
    ],
    codeTitle: "Ключевая форма",
    code: '{\n  "status": "completed",\n  "data": {\n    "metrics": { ... },\n    "ratios": { ... },\n    "score": { ... },\n    "nlp": { ... },\n    "extraction_metadata": { ... }\n  }\n}',
    bridge: "Один и тот же объект результата работает для UI, history и API-интеграций."
  },
  {
    role: "backup",
    layout: "split",
    tag: "Приложение 6",
    title: "Два уровня аналитики: deterministic core и AI-layer",
    subtitle: "Разделение уровней делает продукт одновременно explainable и resilient.",
    leftTitle: "Уровень 1 — deterministic core",
    leftBullets: [
      "Извлечение данных из PDF, таблиц и OCR.",
      "Расчёт коэффициентов и score по формальным правилам.",
      "Работа даже при недоступности внешнего LLM."
    ],
    rightTitle: "Уровень 2 — AI interpretation",
    rightCards: [
      { title: "Risks", body: "NLP-риски и key factors поверх цифр.", accent: "emerald" },
      { title: "Recommendations", body: "3–5 рекомендаций с привязкой к метрикам.", accent: "cyan" },
      { title: "Graceful degrade", body: "Сбой AI не разрушает базовый результат.", accent: "amber" }
    ]
  },
  {
    role: "backup",
    layout: "split",
    tag: "Приложение 7",
    title: "Runtime-контур: от локальной простоты к устойчивому worker-based исполнению",
    subtitle: "Это инженерный слой, который влияет и на демонстрацию, и на будущую эксплуатацию.",
    leftTitle: "background",
    leftBullets: ["Минимальная инфраструктура.", "Удобно для локальной разработки.", "Safe path для простых сценариев."],
    rightTitle: "celery + Redis",
    rightCards: [
      { title: "Worker", body: "Тяжёлая обработка уходит из API-слоя.", accent: "emerald" },
      { title: "Repeatable demo", body: "Подходит для contest smoke и репетиций.", accent: "cyan" },
      { title: "Professional path", body: "Ближе к реальному B2B execution contour.", accent: "amber" }
    ]
  },
  {
    role: "backup",
    layout: "split",
    tag: "Приложение 8",
    title: "Real-time UX: WebSocket как основной путь, polling как страховка",
    subtitle: "Пользовательский опыт тоже построен вокруг устойчивости, а не одного fragile happy path.",
    leftTitle: "Основной путь",
    leftBullets: ["upload -> task_id", "ws/{task_id} -> extracting / scoring / analyzing", "completed -> полный результат в реальном времени"],
    rightTitle: "Fallback path",
    rightCards: [
      { title: "GET /result/{task_id}", body: "Статус и результат доступны без WebSocket.", accent: "cyan" },
      { title: "cancelling / cancelled", body: "Контракт учитывает жизненный цикл задачи.", accent: "amber" },
      { title: "Устойчивость UX", body: "Интерфейс не разваливается при сетевой нестабильности.", accent: "emerald" }
    ]
  },
  {
    role: "backup",
    layout: "split",
    tag: "Приложение 9",
    title: "History и status lifecycle делают результат воспроизводимым во времени",
    subtitle: "Для профессионального продукта важно не только получить отчёт, но и уметь к нему вернуться и сравнить его с другими запусками.",
    leftTitle: "Что хранится",
    leftBullets: [
      "task_id, created_at, score, risk_level, filename.",
      "Полный result object для открытия завершённого анализа.",
      "Состояния processing, completed, failed, cancelled и другие статусы контуров."
    ],
    rightTitle: "Практический эффект",
    rightCards: [
      { title: "Повторное открытие", body: "Кейс можно показать заново без нового запуска.", accent: "cyan" },
      { title: "Сравнение", body: "История усиливает анализ по времени и по документам.", accent: "emerald" },
      { title: "Auditability", body: "В работе остаётся след решения и результата.", accent: "amber" }
    ]
  },
  {
    role: "backup",
    layout: "split",
    tag: "Приложение 10",
    title: "Два формата поставки усиливают B2B-состоятельность продукта",
    subtitle: "Одинаково важно уметь быстро запустить пилот и дать клиенту закрытый контур, если это требуется.",
    leftTitle: "Облачный сценарий",
    leftBullets: ["Быстрый запуск и короткий путь до proof of value.", "Удобен для пилотов и небольших команд.", "Хорош как стартовый коммерческий вход."],
    rightTitle: "Частный сценарий",
    rightCards: [
      { title: "Локальное размещение", body: "Подходит для чувствительных документов и закрытых контуров.", accent: "emerald" },
      { title: "Выше доверие", body: "Сильнее выглядит для банков и risk-sensitive клиентов.", accent: "cyan" },
      { title: "Выше чек", body: "Поддерживает отдельную корпоративную ценность продукта.", accent: "amber" }
    ]
  },
  {
    role: "backup",
    layout: "reference",
    tag: "Приложение 11",
    title: "Безопасность и контроль входного контура уже заложены в продукт",
    subtitle: "Справочный слайд для вопросов об API discipline и управляемости ошибок.",
    columns: 2,
    sections: [
      { title: "Auth", body: "X-API-Key\nDEV_MODE shortcut для локальной разработки", accent: "cyan", mono: true },
      { title: "Validation", body: "PDF magic header\nпустой файл\nлимит 50 МБ", accent: "emerald", mono: true },
      { title: "Error contract", body: "400\n401\n404\n422\n429\n500\n503", accent: "amber", mono: true },
      { title: "Closed contour", body: "частный / локальный режим для более чувствительных клиентов", accent: "red" }
    ]
  },
  {
    role: "backup",
    layout: "split",
    tag: "Приложение 12",
    title: "Contest demo — это не удачный случай, а подготовленный runbook",
    subtitle: "Презентационный контур уже обёрнут в операционную дисциплину, что сильно повышает доверие к проекту.",
    leftTitle: "Что закреплено",
    leftBullets: ["3 эталонных сценария в demo_manifest.json.", "Smoke automation для полного цикла upload -> completed.", "Operator card и backup stand для репетиций и показа."],
    rightTitle: "Почему это усиливает проект",
    rightCards: [
      { title: "Repeatable", body: "Демо можно прогонять многократно с одним контрактом ожиданий.", accent: "emerald" },
      { title: "Observable", body: "Статусы и ошибки не скрыты, а управляются через runtime path.", accent: "cyan" },
      { title: "Contest-ready", body: "Есть ясный сценарий основного и резервного показа.", accent: "amber" }
    ]
  },
  {
    role: "backup",
    layout: "contrast",
    tag: "Приложение 13",
    title: "Эталонные demo-сценарии покрывают три ключевых режима продукта",
    subtitle: "Это не только красиво для защиты, но и полезно как regression-набор для дальнейшей разработки.",
    stats: [
      { value: "text_single", label: "текстовый PDF", accent: "cyan", w: 2.6 },
      { value: "scanned_single", label: "OCR-heavy документ", accent: "emerald", w: 2.6 },
      { value: "multi_period", label: "несколько периодов", accent: "amber", w: 2.6 }
    ],
    lowerPanels: [
      { title: "Инженерный смысл", body: "Сценарии работают как публичное доказательство продукта и как regression-lock для самых важных потоков.", accent: "emerald" },
      { title: "Защитный смысл", body: "Жюри видит не просто интерфейс, а продукт, который умеет стабильно воспроизводить демонстрацию.", accent: "cyan" }
    ]
  },
  {
    role: "backup",
    layout: "split",
    tag: "Приложение 14",
    title: "Многопериодный режим даёт ценность выше разового разбора отчёта",
    subtitle: "Это важный переход от единичной автоматизации к инструменту мониторинга и сравнения динамики.",
    leftTitle: "Что происходит",
    leftBullets: [
      "Несколько отчётов одной компании собираются в одну session.",
      "Периоды сортируются хронологически.",
      "Для каждого периода сохраняются ratios, score, risk_level и extraction metadata."
    ],
    rightTitle: "Почему это полезно",
    rightCards: [
      { title: "Trend view", body: "Можно видеть направление, а не только статичную фотографию состояния.", accent: "emerald" },
      { title: "Monitoring", body: "Подходит для повторяемого внутреннего и клиентского анализа.", accent: "cyan" },
      { title: "Robustness", body: "Частичные ошибки периода не обнуляют ценность всей сессии.", accent: "amber" }
    ]
  },
  {
    role: "backup",
    layout: "reference",
    tag: "Приложение 15",
    title: "Ценность NeoFin AI по ролям и типам клиентов",
    subtitle: "Справочный слайд для разговоров о клиентах и прикладных сценариях использования.",
    columns: 2,
    sections: [
      { title: "Финансовая команда", body: "Меньше ручной подготовки\nБыстрее материалы для решений\nСтандартизированный результат", accent: "cyan" },
      { title: "Аудитор / консультант", body: "Быстрее первичный разбор\nБолее единый вход в экспертную работу\nМеньше механической рутины", accent: "emerald" },
      { title: "Банк / риск-контур", body: "Traceability\nПовторяемость\nИнтерес к закрытому режиму", accent: "amber" },
      { title: "Средний бизнес", body: "Ускорение внутреннего анализа\nПовторяемый workflow\nИстория запусков и контроль статусов", accent: "cyan" }
    ]
  },
  {
    role: "backup",
    layout: "contrast",
    tag: "Приложение 16",
    title: "Экономика проекта опирается на повторяемую ценность, а не на hype",
    subtitle: "Справочный слайд для вопросов о бизнес-модели без искусственно раздутых прогнозов.",
    stats: [
      { value: "B2B", label: "основная выручка через команды с регулярным потоком документов", accent: "emerald", w: 2.7 },
      { value: "SaaS + corporate", label: "сервисный и корпоративный формат", accent: "cyan", w: 2.8 },
      { value: "Time saved", label: "главный носитель ценности и цены", accent: "amber", w: 2.6 }
    ],
    lowerPanels: [
      { title: "Что продаётся на самом деле", body: "Сокращение времени, снижение ручной нагрузки, более управляемый и объяснимый процесс первичного анализа.", accent: "emerald" },
      { title: "Почему модель реалистична", body: "Не нужен массовый consumer traffic: ценность создаётся в регулярном B2B-workflow с дорогим часом специалиста.", accent: "cyan" }
    ]
  },
  {
    role: "backup",
    layout: "reference",
    tag: "Приложение 17",
    title: "Риски, ownership и контакт для следующего шага",
    subtitle: "Финальный backup-слайд перед чистым «Спасибо за внимание».",
    columns: 2,
    sections: [
      { title: "Ключевые риски", body: "Сложные PDF и OCR\nДлинный B2B sales cycle\nТребования к безопасности\nЗависимость стоимости AI от провайдера", accent: "red" },
      { title: "Ответ проекта", body: "Confidence filter\nDeterministic core\nPrivate contour\nManifest-driven demo и regression", accent: "emerald" },
      { title: "Ownership", body: "Автор / lead developer\nАрхитектура продукта\nDemo contour\nProduct packaging", accent: "cyan" },
      { title: "Контакт", body: `Автор: ${CONTACT.author}\nEmail: ${CONTACT.email}\nTelegram: ${CONTACT.telegram}\nGitHub: ${CONTACT.github}`, accent: "amber" }
    ],
    bridge: "Следующий логичный шаг после конкурса — пилот на реальном потоке отчётности и проверка экономии времени в живом процессе клиента."
  },
  {
    role: "final",
    layout: "thanks",
    tag: "Финал",
    title: "Спасибо за внимание",
    subtitle: "NeoFin AI — объяснимый финансовый анализ PDF-отчётности для профессионального контура.",
    thanksLead: "Буду рад вопросам, обратной связи и обсуждению пилота."
  }
];

const DECK = [...MAIN_STORY, ...BACKUP];

module.exports = {
  CONTACT,
  DECK,
};
