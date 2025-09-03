# Economic Calendar 2001–2025 (until July 31, 2025)

The project compiles an economic calendar by year (2001–2025, for 2025 — until July 31) from official sources and prioritized providers.  
The output format is a compact `csv.gz` file with UTC timestamps.

---

## Coverage

- **Countries and regions:** United States (US), Euro Area/EA (including key countries DE/FR/IT/ES), United Kingdom (UK), Switzerland (CH).
- **Event importance:** only `medium` and `high` are included. The importance filter is strictly enforced during validation.
- **Special importance rules:**
  - **US:**
    - FOMC minutes and statements — always `medium`.
    - ISM PMI (Manufacturing/Services/Composite) — always `high`.
  - **ECB:** rate decisions — `high`; post-decision press conferences — `high`. Any unscheduled events — `high`.
  - **Euro Area:** Unemployment Rate — `high`.
  - **UK and CH:** all monetary policy events — `medium`.

---

## Sources and Provider Priority

Priority when collecting (`--providers all`):

`bls, bea, eurostat, ecb, ons, destatis, insee, istat, ine, ism, spglobal, snb, fso_seco, kof, procure_ch, census, fed_ip, confboard, umich, fomc`

**Note:** some providers may be integrated as “stubs” (interface ready, data population staged). In any case, the priority and structure are already incorporated into the pipeline.

---

## Data Formats

### Input CSV (`manual_events.csv`)

**Minimum columns** (order not important):
- `date_local` — YYYY-MM-DD (local release date)
- `time_local` — HH:MM (local time; may be empty)
- `tz` — IANA timezone (e.g., `America/New_York`, `Europe/Zurich`); if empty — source-specific rules or UTC are applied.
- `country` — US, EA, DE, FR, IT, ES, UK, CH
- `importance` — `medium` or `high`
- `title` — event name
- `source_url` — link to the primary source (preferably a domain from `official_domains` in `config.yaml`)
- Optional: `ticker`, `notes`, `certainty`

**Optional fields:**
- `certainty`:
  - `estimated` — no exact time from the primary source, time set via rule/heuristic
  - `secondary` — exact time taken from Reuters/Bloomberg (primary site did not provide it)
  - Empty = confirmed time from the primary source.
- `notes` can contain manual importance overrides: `impact_override=high|medium`

---

### Output Calendar (`calendar_<year>.csv.gz`)

**Required columns:**
- `datetime_utc`, `event`, `country`, `impact`

**Optional:**
- `certainty`, `ticker`, `source_url`, `notes`

Format: `csv.gz` (gzip-compressed CSV).  
Most analytical tools can read `*.csv.gz` directly.  
For Excel viewing, decompress:
- **macOS/Linux:** `gunzip -c calendar_2001.csv.gz > calendar_2001.csv`
- **Windows (PowerShell):** `tar -xzf .\calendar_2001.csv.gz`

---

## UTC Time Conversion

- Uses IANA zoneinfo, accounting for DST changes and “spring forward” gaps.
- Handles `fold=0/1` and non-existent local times (DST change days) by shifting to the nearest valid moment.
- If `tz` is missing and no rule applies — default to UTC (specifying `tz` is recommended).
- If time is from Reuters/Bloomberg — mark `certainty=secondary`.
- If time is set via rules — `certainty=estimated`.

---

## Metrics in the Report

**Backtest Suitability** (integrated metric for backtesting suitability) = weighted sum:
- **Authenticity** — share of records from official domains/primary sources
- **Timing** — share of records with confirmed primary time (excluding `estimated`/`secondary`)

Weights come from `config.yaml` → `weights` (default: 0.95 / 0.05).  
Coverage is not used.

---

## Hashes, Manifest, and Bundles

- `manifest_<year>.json` — SHA-256 of all artifacts for the year (calendar, report, `state.json`, `config.yaml`)
- `bundle_<year>.tar.gz` — complete “snapshot” of the year for transfer/backup (calendar, report, manifest, `state.json`, `config.yaml`)
- `state.json` — pipeline state: artifacts for the year, `updated_at`, and input signatures:
  - `inputs.year_slice_sha256` — SHA-256 of the parsed CSV slice for the year (filtered by `date_local` starting with `${year}-`), stable to column reordering
  - `inputs.config_sha256` — SHA-256 of the `config.yaml` content

**Hashes 101 — how to check SHA-256 locally:**
- **Windows (CMD):** `certutil -hashfile file.ext SHA256`
- **Windows (PowerShell):** `Get-FileHash .\file.ext -Algorithm SHA256`
- **macOS/Linux:** `shasum -a 256 file.ext` or `sha256sum file.ext`

---

## Commands

### Quick Start
```bash
python -m venv .venv
. .venv/bin/activate                # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Yearly Assembly
```bash
# Dry run (no files written)
python core.py assemble --year 2001 --providers all --dry-run

# Full run for the year
python core.py run --year 2001 --bundle
```

**Separate stages:**
```bash
python core.py validate --year 2001 --infile manual_events.csv
python core.py build    --year 2001 --infile manual_events.csv --outfile calendar_2001.csv.gz
python core.py report   --year 2001 --calendar calendar_2001.csv.gz
python core.py bundle   --year 2001
```

**Parameters:**
- `--providers` — select a subset of sources (`all` = by priority above)
- `--cache-dir` — cache directory for providers
- `--dry-run` — in `assemble`: collect everything in memory and display a summary without writing files

---

## Validation Rules

- Only `importance ∈ {medium, high}` (drop all `low`)
- Apply manual overrides from `notes`: `impact_override=...`
- If exact time from the primary source cannot be determined — `certainty=estimated`
- If time is from Reuters/Bloomberg — `certainty=secondary`

---

## Progress Saving and Resuming After Interruption

- After each key stage, `state.json` is updated.
- Manifest and report are recalculated together to avoid desynchronization.
- To resume in a new session, just load `bundle_<year>.tar.gz` (or individual artifacts) — the pipeline will skip completed steps based on hashes and state.

---

## Configuration (`config.yaml`)

Minimal valid config:
```yaml
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
time_rules: {}
```

---

## Environment and Reproducibility

- Python 3.11 (or container `python:3.11-slim`)
- Packages pinned in `requirements.txt` (including `tzdata`)
- Dockerfile available for fully reproducible environment

---

## FAQ

**Why `csv.gz`?**  
It’s smaller, faster to transfer, and natively readable by pandas/R/CLI tools.

**Can I load only `calendar_<year>.csv.gz` and continue?**  
Yes — for reporting/merging years, that’s sufficient.  
For re-validation/filling, it’s better to have `manual_events.csv` and `config.yaml` (and/or `bundle_<year>.tar.gz`).

**What about 2025?**  
Covers January 1 – July 31, 2025.

---

## Timezones and Aliases
In `config.yaml` you can set `tz_aliases` (e.g., `ET → America/New_York`, `CET → Europe/Berlin`).  
If `tz` is missing or invalid, UTC is used and a warning is sent to `stderr`.

---

## Robust CSV Handling

- Auto-detect encoding: try `utf-8`, `utf-8-sig`, `cp1251`, `latin-1`
- Normalize headers: lowercase + aliases (`date→date_local`, `time→time_local`, `timezone→tz`, `event→title`, `impact→importance`, `url/source→source_url`, etc.)
- Validate required columns and rows; drop rows with missing required fields, invalid dates, or `importance∉{medium,high}`
- Output: `validated_<year>.csv` (snapshot of filtered rows) and `validation_report_<year>.json` (summary)
- Won’t crash on a “broken” CSV — invalid rows are dropped, remaining ones are processed

---

## Reproducible Builds (Stable Hashes)

- `calendar_<year>.csv.gz` written with fixed `mtime=0` in the gzip header → identical SHA-256 for identical content
- `bundle_<year>.tar.gz` created with normalized metadata (`uid/gid=0`, empty `uname/gname`, `mtime=0`) → stable archive hash

---

## Year Filter

In `validate` and `build`, a strict filter is applied on the `date_local` field for the given `--year`.  
Extra years are dropped and recorded in `validation_report_<year>.json` (`other_years`).

---

## Policy Updates

- **Authenticity** is interpreted as official source: events with `certainty=estimated` from official domains are considered **official** the same as `confirmed`; `secondary` = Reuters/Bloomberg, etc.
- **Backtest suitability** uses weights from `config.yaml` (`weights.authenticity_weight`, `weights.timing_weight`). Defaults: **0.95** and **0.05** respectively.
- **Exclusions** from `config.yaml` are applied during `validate` and `build` stages.  
  Events matching `titles_exact` or `weekly_series` are automatically excluded.

---

## Official Source Logic and Auto-Confirm

**Official source** = union of:
- `official_domains` — explicit list (statistical agencies, etc.)
- `gov_like_patterns` — patterns for central bank domains (Fed/FRB, ECB, Bundesbank, Banque de France, Banca d’Italia, Banco de España, SNB, BoE)

**Report rules (Authenticity):**
- `secondary` — unofficial
- `confirmed` — official
- `estimated` or empty — official **only if** domain ∈ (`official_domains` ∪ `gov_like_patterns`)

**Promotion to `confirmed` in build stage:**
- If domain ∈ (`official_domains` ∪ `gov_like_patterns`), **and** timezone is valid, **and** exact `time_local` is provided — then `'' | estimated → confirmed`
- If timezone is invalid/missing — mark as `estimated` and add `tz_fallback=utc` to `notes` (no promotion)

---

## How Importance Is Assigned (via `config.yaml`)

Starting with this version, importance rules are configured in `config.yaml` under the `importance_rules` section.  
The pipeline automatically:
1. Reads manual overrides from `notes` by the key `impact_override` (e.g., `impact_override=high`)
2. Applies rules by country and title pattern (first match wins)
3. Keeps only values from `include_impacts` (default: `high`, `medium`)

**Minimal example block in `config.yaml`:**
```yaml
importance_rules:
  notes_override_key: "impact_override"
  items:
    - name: "US: ISM PMI — high"
      when: { country: US, title_regex: "(?i)\bism\b.*\bpmi\b" }
      set: high

    - name: "US: FOMC minutes/statement — medium"
      when: { country: US, title_regex: "(?i)\bfomc\b.*(minutes|statement)" }
      set: medium

    - name: "US: FOMC press conference — high"
      when: { country: US, title_regex: "(?i)\bfomc\b.*(press\s+conference|news\s+conference)" }
      set: high

    - name: "US: FOMC unscheduled — high"
      when: { country: US, title_regex: "(?i)\bfomc\b.*(unscheduled|intermeeting|emergency|out[-\s]of[-\s]schedule)" }
      set: high

    - name: "ECB: rate decision — high"
      when: { title_regex: "(?i)\becb\b.*(rate|interest).*decision" }
      set: high

    - name: "ECB: press conference — high"
      when: { title_regex: "(?i)\becb\b.*press\s+conference" }
      set: high

    - name: "ECB: unscheduled — high"
      when: { title_regex: "(?i)\becb\b.*(unscheduled|extraordinary|emergency)" }
      set: high

    - name: "EA: Unemployment Rate — high"
      when: { country: EA, title_regex: "(?i)unemployment.*rate" }
      set: high

    - name: "DE: Flash CPI — medium"
      when: { country: DE, title_regex: "(?i)\bflash\b.*\bcpi\b" }
      set: medium

    - name: "UK: monetary policy — medium"
      when: { country: UK, title_regex: "(?i)(rate\s+decision|bank\s+rate|policy\s+rate|monetary\s+policy|mpc\s+meeting)" }
      set: medium

    - name: "CH: monetary policy — medium"
      when: { country: CH, title_regex: "(?i)(rate\s+decision|policy\s+rate|monetary\s+policy|snb\s+policy|snb\s+meeting|snb\s+monetary\s+policy)" }
      set: medium
```

> **Note:** The order of rules matters — the first match is applied.  
> For fine-tuning, you can add your own items to `items` without modifying the code.
