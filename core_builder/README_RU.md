Economic Calendar 2001–2025 (до 31 июля 2025)

Проект собирает экономический календарь по годам (2001–2025, для 2025 — до 31 июля) из официальных источников и приоритезированных провайдеров. Выходной формат — компактный csv.gz с UTC-временем.

Что покрываем

- Страны и регионы: США (US), Еврозона/EA (в т.ч. ключевые страны DE/FR/IT/ES), Великобритания (UK), Швейцария (CH).
- Важность событий: берём только medium и high. Фильтр важности жёстко enforced в валидации.
- Специальные правила важности:
  - США:
    - FOMC minutes и statements — всегда medium.
    - ISM PMI (Manufacturing/Services/Composite) — всегда high.
  - ECB: решения по ставке — high; пресс-конференция после решения — high. Любые внеплановые события — high.
  - Еврозона: Unemployment Rate — high.
  - UK и CH: все ДКП-события — medium.

Источники и приоритет провайдеров

Приоритет при сборе (--providers all):
bls, bea, eurostat, ecb, ons, destatis, insee, istat, ine, ism, spglobal, snb, fso_seco, kof, procure_ch, census, fed_ip, confboard, umich, fomc

Примечание: часть провайдеров может быть интегрирована как «заглушки» (интерфейс готов, наполнение поэтапно). В любом случае, приоритет и структура уже учтены в пайплайне.

Форматы данных

Входной CSV (manual_events.csv)
Минимальный набор колонок (порядок не критичен):
- date_local — YYYY-MM-DD (локальная дата релиза);
- time_local — HH:MM (локальное время; можно пусто);
- tz — IANA-таймзона (например, America/New_York, Europe/Zurich); если пусто — применяются правила по источникам или UTC.
- country — US, EA, DE, FR, IT, ES, UK, CH;
- importance — medium или high;
- title — название события;
- source_url — ссылка на первоисточник (желательно с доменом из official_domains в config.yaml);
- опционально: ticker, notes, certainty.

Примечание (опциональные поля):
- certainty:
  - estimated — точного времени нет у первоисточника, время выставлено по правилу/эвристике;
  - secondary — точное время взято из Reuters/Bloomberg (первичный сайт не дал время).
  Пусто = есть подтверждённое время у первоисточника.
- В notes можно указывать ручные оверрайды важности (опционально): impact_override=high|medium.

Выходной календарь (calendar_<year>.csv.gz)
Строго следующие колонки:
- обязательные: datetime_utc, event, country, impact
- опциональные: certainty, ticker, source_url, notes

Формат — csv.gz (gzip-сжатый CSV). Большинство аналитических инструментов читают *.csv.gz напрямую. Для просмотра в Excel можно распаковать:
macOS/Linux: gunzip -c calendar_2001.csv.gz > calendar_2001.csv
Windows (PowerShell): tar -xzf .\calendar_2001.csv.gz

Конвертация времени в UTC

- Используем IANA zoneinfo с учётом DST/«дыр» весеннего перевода часов.
- Обрабатываем fold=0/1 и нестандартные случаи (не существующее локальное время в день смены времени): сдвигаем к ближайшему корректному моменту.
- Если tz не указана и нет правила — по умолчанию считаем UTC (рекомендуется указывать tz).
- Если время взято из Reuters/Bloomberg — помечаем certainty=secondary. Если выставлено по правилу — certainty=estimated.

Метрики в отчёте

Backtest Suitability (интегральная оценка пригодности для бэктеста) = взвешенная сумма:
- Authenticity — доля записей с официальными доменами/первичными источниками;
- Timing — доля записей с подтверждённым первичным временем (без estimated/secondary).

Веса берутся из config.yaml → weights (по умолчанию 0.95 / 0.05). Coverage не используется.

Хэши, манифест и бандлы

- manifest_<year>.json — SHA-256 всех артефактов за год (календарь, отчёт, state.json, config.yaml).
- bundle_<year>.tar.gz — собранный «слепок» года для переноса/резервного копирования (календарь, отчёт, манифест, state.json, config.yaml).
- state.json — состояние пайплайна: артефакты за год, updated_at и подписи входов:
  - inputs.year_slice_sha256 — SHA-256 среза входа за год, вычисленного из **распарсенного CSV** (фильтр по столбцу `date_local` начинается с `${year}-`), устойчиво к перестановке колонок;
  - inputs.config_sha256 — SHA-256 содержимого config.yaml.

Hashes 101 — как проверить SHA-256 локально

- Windows (CMD):  certutil -hashfile file.ext SHA256
- Windows (PowerShell):  Get-FileHash .\file.ext -Algorithm SHA256
- macOS/Linux:  shasum -a 256 file.ext  или  sha256sum file.ext

Сверьте полученный хэш с manifest_<year>.json или с хэшем, указанным в отчёте.

Команды

Быстрый старт
python -m venv .venv
. .venv/bin/activate                # Windows: .venv\Scripts\activate
pip install -r requirements.txt

Сбор по году
# вначале можно «сухой прогон» (не пишет файлы)
python core.py assemble --year 2001 --providers all --dry-run
# полноценный прогон за год
python core.py run --year 2001 --bundle

Доступны также отдельные стадии:
python core.py validate --year 2001 --infile manual_events.csv
python core.py build    --year 2001 --infile manual_events.csv --outfile calendar_2001.csv.gz
python core.py report   --year 2001 --calendar calendar_2001.csv.gz
python core.py bundle   --year 2001

Параметры:
- --providers — выбрать подмножество источников (all — по приоритету выше);
- --cache-dir — директория кэша для провайдеров;
- --dry-run — в assemble: собрать всё в памяти и показать сводку без записи.

Правила валидации

- Пропускаем только importance ∈ {medium, high} (любые low отсекаются).
- Учёт ручных оверрайдов важности через notes: impact_override=... (если указан).
- Если не удаётся установить точное время у первоисточника — certainty=estimated.
- Если время из Reuters/Bloomberg — certainty=secondary.

Сохранение прогресса и возобновление после обрыва

- После каждой ключевой стадии обновляется state.json.
- Манифест и отчёт пересчитываются «одним махом», чтобы не было рассинхрона.
- Для возобновления в новой сессии достаточно загрузить сюда bundle_<year>.tar.gz (или артефакты по отдельности) — пайплайн пропустит уже сделанные шаги по хэшам и состоянию.

Конфигурация (config.yaml)

Минимальный валидный конфиг:
official_domains:
  domains:
    - federalreserve.gov
    - ecb.europa.eu
    - bls.gov
    - bea.gov
    - eurostat.ec.europa.eu
    - ons.gov.uk
    - bankofengland.co.uk
    - snb.ch
    - destatis.de
    - insee.fr
    - istat.it
    - ine.es
    - ismworld.org
    - spglobal.com
weights:
  authenticity: 0.95
  timing: 0.05
time_rules: {}      # опционально, правила времени по событиям/источникам

Окружение и воспроизводимость

- Python 3.11 (или контейнер python:3.11-slim).
- Пакеты закреплены версиями в requirements.txt (включая tzdata).
- Dockerfile доступен для полностью воспроизводимого окружения.

Частые вопросы

Почему csv.gz?
Компактнее, быстрее передаётся, нативно читается pandas/R/полезными утилитами.

Можно ли загрузить только calendar_<year>.csv.gz и продолжить?
Да — для отчёта/склейки годов этого достаточно. Но для пере-валидации/дозаполнения лучше иметь manual_events.csv и config.yaml (и/или bundle_<year>.tar.gz).

С 2025 годом что?
Собираем период с 1 января по 31 июля 2025 включительно.

**Таймзоны и алиасы:** в `config.yaml` можно задать `tz_aliases` (например, `ET → America/New_York`, `CET → Europe/Berlin`). Если `tz` не указана или некорректна, используется fallback: UTC, а в stderr будет предупреждение.


## Робастная обработка CSV
- Автодетект кодировки: пробуем `utf-8`, `utf-8-sig`, `cp1251`, `latin-1`.
- Нормализация заголовков: приводим к нижнему регистру и алиасы (`date→date_local`, `time→time_local`, `timezone→tz`, `event→title`, `impact→importance`, `url/source→source_url` и др.).
- Проверка обязательных колонок и строк; записи с пустыми обязательными полями, неверной датой или `importance∉{medium,high}` — **отбрасываются**. 
- Результат валидации: `validated_<year>.csv` (снимок строк, прошедших фильтры) и `validation_report_<year>.json` (сводка).
- Сборка не падает на «кривом» CSV — невалидные строки исключаются, остальное собирается.


## Репродюсируемые сборки (stable hashes)
- Выходной `calendar_<year>.csv.gz` пишется с фиксированным `mtime=0` в заголовке gzip → одинаковый SHA-256 при одинаковом содержимом.
- Бандл `bundle_<year>.tar.gz` создаётся с нормализованными метаданными (`uid/gid=0`, пустые `uname/gname`, `mtime=0` для файлов) → стабильный хэш архива.


## Фильтр по году
Во `validate` и `build` происходит жёсткий срез по полю `date_local` на указанный `--year`. Лишние годы отбрасываются и фиксируются в `validation_report_<year>.json` (`other_years`).

### Обновления политики (актуально)
- **Authenticity** трактуется как официальность источника: события с `certainty=estimated` из официальных доменов считаются **официальными** наравне с `confirmed`; `secondary` — это Reuters/Bloomberg и т.п.
- **Backtest suitability** использует веса из `config.yaml` (`weights.authenticity_weight`, `weights.timing_weight`). Дефолты проекта сейчас: **0.95** и **0.05** соответственно.
- **Exclusions (жёсткие исключения)** из `config.yaml` применяются **на стадиях `validate` и `build`**. События, попавшие под `titles_exact` или `weekly_series`, автоматически исключаются из пайплайна.



_Прим.: По умолчанию веса для Backtest Suitability — authenticity: 0.95, timing: 0.05._

## Логика «официальности» источника и auto-confirm

**Официальный источник** в отчёте трактуется как объединение двух множеств:
- `official_domains` — явный список (статведы и т.п., см. `config.yaml`).
- `gov_like_patterns` — паттерны доменов центробанков (Fed/FRB, ECB, Bundesbank, Banque de France, Banca d’Italia, Banco de España, SNB, BoE).

Правила в отчёте (Authenticity):
- `secondary` — неофициально.
- `confirmed` — официально.
- `estimated` или пусто — официально **только если** домен ∈ (`official_domains` ∪ `gov_like_patterns`).

Правила повышения до `confirmed` в сборке (stage_build):
- Если домен ∈ (`official_domains` ∪ `gov_like_patterns`), **и** таймзона валидна, **и** задано точное `time_local` — тогда `'' | estimated → confirmed`.
- Если таймзона невалидна/пустая — запись помечается `estimated` и в `notes` добавляется `tz_fallback=utc` (повышения нет).

### Как присваивается важность (через `config.yaml`)

Начиная с этой версии, правила важности настраиваются в `config.yaml` в секции `importance_rules`.
Пайплайн автоматически:
1) читает ручной оверрайд из `notes` по ключу `impact_override` (например: `impact_override=high`),  
2) применяет правила по стране и шаблонам заголовка (первое совпадение выигрывает),  
3) оставляет только значения из `include_impacts` (по умолчанию: `high`, `medium`).

Минимальный пример блока в `config.yaml`:

```yaml
importance_rules:
  notes_override_key: "impact_override"
  items:
    - name: "US: ISM PMI — high"
      when: { country: US, title_regex: "(?i)\\bism\\b.*\\bpmi\\b" }
      set: high

    - name: "US: FOMC minutes/statement — medium"
      when: { country: US, title_regex: "(?i)\\bfomc\\b.*(minutes|statement)" }
      set: medium

    - name: "US: FOMC press conference — high"
      when: { country: US, title_regex: "(?i)\\bfomc\\b.*(press\\s+conference|news\\s+conference)" }
      set: high

    - name: "US: FOMC unscheduled — high"
      when: { country: US, title_regex: "(?i)\\bfomc\\b.*(unscheduled|intermeeting|emergency|out[-\\s]of[-\\s]schedule)" }
      set: high

    - name: "ECB: rate decision — high"
      when: { title_regex: "(?i)\\becb\\b.*(rate|interest).*decision" }
      set: high

    - name: "ECB: press conference — high"
      when: { title_regex: "(?i)\\becb\\b.*press\\s+conference" }
      set: high

    - name: "ECB: unscheduled — high"
      when: { title_regex: "(?i)\\becb\\b.*(unscheduled|extraordinary|emergency)" }
      set: high

    - name: "EA: Unemployment Rate — high"
      when: { country: EA, title_regex: "(?i)unemployment.*rate" }
      set: high

    - name: "DE: Flash CPI — medium"
      when: { country: DE, title_regex: "(?i)\\bflash\\b.*\\bcpi\\b" }
      set: medium

    - name: "UK: monetary policy — medium"
      when: { country: UK, title_regex: "(?i)(rate\\s+decision|bank\\s+rate|policy\\s+rate|monetary\\s+policy|mpc\\s+meeting)" }
      set: medium

    - name: "CH: monetary policy — medium"
      when: { country: CH, title_regex: "(?i)(rate\\s+decision|policy\\s+rate|monetary\\s+policy|snb\\s+policy|snb\\s+meeting|snb\\s+monetary\\s+policy)" }
      set: medium
```

> Примечание: порядок правил важен — применяется первое совпадение.  
> Для тонкой настройки можно добавлять свои элементы в `items` без правки кода.
