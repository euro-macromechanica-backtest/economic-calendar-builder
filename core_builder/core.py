#!/usr/bin/env python3
"""
Compact economic-calendar pipeline (flat layout).

Commands:
  python core.py assemble --year 2001 [--providers ...] [--dry-run]
  python core.py run      --year 2001 --infile manual_events.csv [--bundle]
  python core.py validate --year 2001 --infile manual_events.csv
  python core.py build    --year 2001 --infile manual_events.csv --outfile calendar_2001.csv.gz
  python core.py report   --year 2001 --calendar calendar_2001.csv.gz --outfile year_report_2001.md
  python core.py bundle   --year 2001

Artifacts are written to the current directory (flat). State is tracked in state.json.
"""
import argparse, json, os, sys, re, time, gzip, hashlib, tarfile
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
STATE = HERE / "state.json"

# --- Helpers ---
def sha256_file(p: Path) -> str:
    h=hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def _to_utc_iso(date_local:str, time_local:str|None, tzname:str|None) -> str:
    from datetime import datetime, time, timezone, timedelta
    d = datetime.strptime(date_local, "%Y-%m-%d").date()
    t = time(0,0)
    if time_local:
        try:
            hh, mm = map(int, str(time_local).split(":")[:2])
            t = time(hh, mm)
        except Exception:
            pass
    naive = datetime(d.year, d.month, d.day, t.hour, t.minute, 0)
    if tzname:
        try:
            tzinfo = ZoneInfo(tzname)
        except Exception:
            print(f"[warn] invalid tz '{tzname}', fallback UTC", file=sys.stderr)
            tzinfo = timezone.utc
    else:
        tzinfo = timezone.utc
    local = naive.replace(tzinfo=tzinfo)
    try:
        dt_utc = local.astimezone(timezone.utc)
    except Exception:
        dt_utc = (local + timedelta(hours=1)).astimezone(timezone.utc)
    return dt_utc.replace(tzinfo=timezone.utc).isoformat()

def _read_csv_with_fallback(infile: Path):
    encodings = ['utf-8','utf-8-sig','cp1251','latin-1']
    last_err = None
    for enc in encodings:
        try:
            df = pd.read_csv(infile, sep=None, engine='python', dtype=str, encoding=enc)
            return df, enc
        except Exception as e:
            last_err = e
    raise ValueError(f'Failed to read CSV with {encodings}: {last_err}')

def _normalize_headers(df):
    aliases = {'date':'date_local','dt_local':'date_local','local_date':'date_local',
               'time':'time_local','local_time':'time_local',
               'timezone':'tz','time_zone':'tz',
               'cntry':'country',
               'event':'title','name':'title',
               'impact':'importance',
               'url':'source_url','source':'source_url'}
    df.columns = [aliases.get(str(c).strip().lower(), str(c).strip().lower()) for c in df.columns]
    return df

def _ensure_columns(df):
    required = ['date_local','country','importance','title']
    optional = ['time_local','tz','ticker','notes','source_url','certainty']
    for c in required+optional:
        if c not in df.columns:
            df[c] = ''
    return df, required, optional

def _drop_invalid_rows(df, required):
    from datetime import datetime
    total = len(df)
    df['importance'] = df['importance'].astype(str).str.strip().str.lower()
    allowed = {'medium','high'}
    mask_imp = df['importance'].isin(allowed)
    def _is_date_ok(s):
        s = str(s).strip()
        try:
            datetime.strptime(s, '%Y-%m-%d'); return True
        except Exception:
            return False
    mask_date = df['date_local'].map(_is_date_ok)
    mask_req = pd.Series(True, index=df.index)
    for c in required:
        mask_req &= df[c].astype(str).str.strip().ne('')
    keep = mask_imp & mask_date & mask_req
    out = df.loc[keep].copy().reset_index(drop=True)
    stats = {'total_rows': int(total), 'kept_rows': int(len(out)), 'dropped_rows': int((~keep).sum()),
             'dropped_reasons': {'bad_importance_or_low': int((~mask_imp).sum()),
                                 'bad_date_format': int((~mask_date).sum()),
                                 'missing_required_fields': int((~mask_req).sum())}}
    return out, stats

def canonicalize_tz(tz_str: str|None, cfg: dict) -> str|None:
    if not tz_str:
        return None
    tz_s = str(tz_str).strip()
    if not tz_s:
        return None
    aliases = (cfg or {}).get("tz_aliases", {}) or {}
    builtins = {
        "UTC":"UTC","GMT":"UTC",
        "CET":"Europe/Berlin","CEST":"Europe/Berlin","BST":"Europe/London",
        "ET":"America/New_York","EST":"America/New_York","EDT":"America/New_York",
        "PT":"America/Los_Angeles","PST":"America/Los_Angeles","PDT":"America/Los_Angeles"
    }
    return aliases.get(tz_s) or aliases.get(tz_s.upper()) or builtins.get(tz_s.upper()) or tz_s

def load_config_dict() -> dict:
    try:
        return yaml.safe_load((HERE/"config.yaml").read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

def get_official_domains():
    """Return set of official domains from config.yaml; fallback to built-in default."""
    cfg = load_config_dict()
    od = cfg.get("official_domains", [])
    if isinstance(od, dict):
        doms = od.get("domains", [])
    else:
        doms = od
    if isinstance(doms, list) and doms:
        return set([str(d).lower().lstrip("www.") for d in doms])
    return {
        'federalreserve.gov','frb.org','bls.gov','bea.gov','census.gov',
        'ecb.europa.eu','eurostat.ec.europa.eu','ec.europa.eu',
        'ons.gov.uk','bankofengland.co.uk',
        'snb.ch','seco.admin.ch','bfs.admin.ch','kof.ethz.ch','procure.ch',
        'destatis.de','insee.fr','istat.it','ine.es',
        'ismworld.org','spglobal.com','pmi.spglobal.com'
    }

def get_exclusions():
    """Return dict: {CC: {'titles_exact': set(), 'weekly_series': set()}}."""
    cfg = load_config_dict()
    exc = cfg.get("exclusions", {}) or {}
    norm = {}
    for country, block in exc.items():
        if not isinstance(block, dict):
            continue
        te = set([str(x).strip().lower() for x in (block.get("titles_exact") or [])])
        ws = set([str(x).strip().lower() for x in (block.get("weekly_series") or [])])
        norm[str(country).strip().upper()] = {"titles_exact": te, "weekly_series": ws}
    return norm


def _domain_from_url(url: str) -> str:
    """Return normalized host without 'www.' and port, lowercased."""
    try:
        from urllib.parse import urlparse
        host = urlparse(str(url)).netloc.lower()
        if ':' in host:
            host = host.split(':',1)[0]
        if host.startswith('www.'):
            host = host[4:]
        return host
    except Exception:
        return ''

def get_govlike_patterns():
    """Return list of regex patterns from config.yaml (gov_like_patterns) or sensible defaults."""
    try:
        cfg = load_config_dict()
        pats = cfg.get('gov_like_patterns', None)
        if isinstance(pats, list) and pats:
            return [str(p) for p in pats]
    except Exception:
        pass
    # Defaults cover many official/stat/CB TLDs and key hosts
    return [
        r'.*\.gov$',
        r'.*\.gov\.[a-z]{2,3}$',
        r'.*\.gouv\.fr$',
        r'.*\.go\.jp$',
        r'.*\.gov\.uk$',
        r'.*\.admin\.ch$',
        r'.*\.europa\.eu$',
        r'.*\.boj\.or\.jp$',
        r'.*\.rba\.gov\.au$',
        r'.*\.rbnz\.govt\.nz$',
        r'.*\.bankofcanada\.ca$',
        r'.*\.banxico\.org\.mx$',
        r'.*\.istat\.it$',
        r'.*\.insee\.fr$',
        r'.*\.ons\.gov\.uk$',
        r'.*\.destatis\.de$',
        r'.*\.census\.gov$',
        r'.*\.bls\.gov$',
        r'.*\.bea\.gov$',
        r'.*\.ecb\.europa\.eu$',
        r'.*\.snb\.ch$',
    ]

def _is_officialish_host(host: str, official_domains: set[str]|list[str]|None=None, govlike_pats: list[str]|None=None, alias_domains: set[str]|list[str]|None=None, canonical_map: dict[str,str]|None=None) -> bool:
    host = _canonicalize_host((host or '').lower(), canonical_map)
    if not host:
        return False
    def _match_base(host, base):
        base = str(base).lower().lstrip('.')
        return host == base or host.endswith('.'+base)
    if official_domains:
        for base in official_domains:
            if _match_base(host, base):
                return True
    if alias_domains:
        for base in alias_domains:
            if _match_base(host, base):
                return True
    for p in (govlike_pats or []):
        try:
            if re.fullmatch(p, host):
                return True
        except re.error:
            if re.search(p, host):
                return True
    return False

def get_alias_domains():
    try:
        cfg = load_config_dict()
        aliases = cfg.get('official_alias_domains', [])
        return [str(a).lower().lstrip('.') for a in aliases if a]
    except Exception:
        return []

def get_canonical_host_map():
    try:
        cfg = load_config_dict()
        m = cfg.get('canonical_host_map', {})
        return {str(k).lower(): str(v).lower() for k,v in (m or {}).items()}
    except Exception:
        return {}

def _canonicalize_host(host: str, canonical_map: dict[str,str]|None=None) -> str:
    h = (host or '').lower()
    if canonical_map:
        # exact match rewrite
        if h in canonical_map:
            return canonical_map[h]
    return h
def get_backtest_weights():
    """Return (auth_w, time_w) from config.yaml; defaults (0.95, 0.05)."""
    try:
        w = load_config_dict().get("weights", {}) or {}
        aw = w.get("authenticity_weight", None)
        tw = w.get("timing_weight", None)
        if isinstance(aw,(int,float)) and isinstance(tw,(int,float)):
            s = aw+tw
            if s>0: return aw/s, tw/s
        a = w.get("authenticity", None)
        t = w.get("timing", None)
        if isinstance(a,(int,float)) and isinstance(t,(int,float)):
            s = a+t
            if s>0: return a/s, t/s
        return 0.95, 0.05
    except Exception:
        return 0.95, 0.05

# --- Collectors stubs (no-op for now) ---
def collect_fomc_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_bls_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_bea_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_eurostat_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_ecb_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_ons_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_destatis_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_insee_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_istat_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_ine_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_ism_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_spglobal_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_snb_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_fso_seco_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_kof_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_procure_ch_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_census_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_fed_ip_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_confboard_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []
def collect_umich_year(year:int, cache_dir:Path|None=None) -> list[dict]: return []

PROVIDERS_REGISTRY = {
    "fomc": collect_fomc_year,
    "bls": collect_bls_year,
    "bea": collect_bea_year,
    "eurostat": collect_eurostat_year,
    "ecb": collect_ecb_year,
    "ons": collect_ons_year,
    "destatis": collect_destatis_year,
    "insee": collect_insee_year,
    "istat": collect_istat_year,
    "ine": collect_ine_year,
    "ism": collect_ism_year,
    "spglobal": collect_spglobal_year,
    "snb": collect_snb_year,
    "fso_seco": collect_fso_seco_year,
    "kof": collect_kof_year,
    "procure_ch": collect_procure_ch_year,
    "census": collect_census_year,
    "fed_ip": collect_fed_ip_year,
    "confboard": collect_confboard_year,
    "umich": collect_umich_year,
}
PROVIDERS_ALL = list(PROVIDERS_REGISTRY.keys())

# --- Stages ---
def stage_collect(year:int, providers:list[str], master_csv:Path, cache_dir:Path|None=None):
    provs = [p.lower() for p in (providers or [])]
    if not provs:
        provs = ["fomc"]
    new_rows = []
    official_domains = get_official_domains()
    for key in provs:
        fn = PROVIDERS_REGISTRY.get(key)
        if not fn:
            print(f"[collect] provider not found: {key}")
            continue
        try:
            rows = fn(year, cache_dir)
            print(f"[collect:{key}] +{len(rows)} rows")
            new_rows.extend(rows)
        except Exception as e:
            print(f"[collect:{key}] error: {e}")
    if new_rows:
        cols = ["date_local","time_local","tz","ticker","country","importance","title","source_url","notes"]
        df_new = pd.DataFrame(new_rows)
        for c in cols:
            if c not in df_new.columns: df_new[c] = ""
        if master_csv.exists() and master_csv.stat().st_size>0:
            df_old = pd.read_csv(master_csv)
            df = pd.concat([df_old, df_new[cols]], ignore_index=True)
        else:
            df = df_new[cols]
        df.to_csv(master_csv, index=False)
    return master_csv, len(new_rows)

def _apply_exclusions(df: pd.DataFrame) -> pd.DataFrame:
    exc = get_exclusions()
    if df.empty or not exc:
        return df
    def _drop(row):
        cc = str(row.get('country','')).strip().upper()
        title = str(row.get('title','')).strip().lower()
        b = exc.get(cc, {})
        if title in (b.get('titles_exact') or set()): return True
        if title in (b.get('weekly_series') or set()): return True
        return False
    mask = df.apply(_drop, axis=1)
    dropped = int(mask.sum())
    if dropped:
        print(f"[exclusions] dropped {dropped} rows")
    return df.loc[~mask].copy()


def _compile_importance_rules(cfg: dict) -> list[dict]:
    """
    Read importance_rules from config.yaml and return a list of compiled items:
    each item is {'country': 'US'|'EA'|..., 'title_regex': compiled regex or None, 'set': 'high'|'medium'}.
    """
    items = []
    try:
        rules = (cfg or {}).get("importance_rules", {}) or {}
        raw_items = rules.get("items") or []
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            country = str((it.get("when") or {}).get("country","")).strip().upper()
            title_rx = (it.get("when") or {}).get("title_regex")
            set_to = str(it.get("set","")).strip().lower()
            if not set_to:
                continue
            cre = None
            if title_rx:
                try:
                    cre = re.compile(title_rx, re.I)
                except Exception:
                    cre = None
            items.append({"country": country, "title_re": cre, "set": set_to})
    except Exception:
        pass
    return items

def _apply_importance_rules(df: pd.DataFrame) -> pd.DataFrame:
    """
    1) honor notes override like 'impact_override=high' (key is configurable via config.yaml)
    2) apply rule list from config.yaml.importance_rules.items in order
    3) clamp to allowed values from config.include_impacts (default {'high','medium'})
    """
    cfg = load_config_dict()
    notes_key = str(((cfg.get("importance_rules") or {}).get("notes_override_key")) or "impact_override").strip()
    allowed = set((cfg.get("include_impacts") or ["high","medium"]))
    rules = _compile_importance_rules(cfg)

    def derive(row):
        imp = str(row.get("importance","")).strip().lower()
        title = str(row.get("title","")).strip()
        cc = str(row.get("country","")).strip().upper()
        notes = str(row.get("notes",""))

        # 1) notes override: key=value anywhere in notes
        if notes_key:
            m = re.search(rf'{re.escape(notes_key)}\s*=\s*(high|medium)', notes, re.I)
            if m:
                return m.group(1).lower()

        # 2) rules: first match wins
        for it in rules:
            if it.get("country") and it["country"] != cc:
                continue
            rx = it.get("title_re")
            if rx is not None and not rx.search(title):
                continue
            # match!
            return it.get("set","").lower() or imp

        return imp

    df = df.copy()
    df["importance"] = df.apply(derive, axis=1).astype(str).str.strip().str.lower()
    # clamp to allowed
    df["importance"] = df["importance"].where(df["importance"].isin(allowed), next(iter(allowed)))
    return df


def stage_validate(year:int, infile:Path):
    df, enc = _read_csv_with_fallback(infile)
    df = _normalize_headers(df)
    df, required, optional = _ensure_columns(df)
    df = _apply_importance_rules(df)
    df, stats = _drop_invalid_rows(df, required)
    mask_year = df['date_local'].astype(str).str.startswith(f"{year}-")
    df = df.loc[mask_year].copy()
    if year == 2025:
        df = df[df["date_local"] <= "2025-07-31"].copy()
    # exclusions
    df = _apply_exclusions(df)
    # simple deduplication: date_local + title + country
    import re as _re
    def _canon_title(_s: str) -> str:
        _s = str(_s or '').strip().lower()
        _s = _s.replace('–','-').replace('—','-')
        _s = _re.sub(r'\s+', ' ', _s)
        _s = _re.sub(r'\s*([/-])\s*', r' \1 ', _s)
        return _s.strip()
    df['__dedup_key'] = (
        df['date_local'].astype(str).str[:10] + '|' +
        df['country'].astype(str).str.strip().str.upper() + '|' +
        df['title'].map(_canon_title)
    )
    before = len(df)
    df = df.drop_duplicates('__dedup_key', keep='first')
    df.drop(columns=['__dedup_key'], inplace=True)
    # end dedup
    df.reset_index(drop=True, inplace=True)
    snap = Path(f"validated_{year}.csv"); df.to_csv(snap, index=False)
    rep = {
        "year": year, "encoding_used": enc, "required_columns": required,
        "kept_rows": int(len(df)),
        "dropped_rows": int(stats["total_rows"] - len(df)),
        "dropped_reasons": stats["dropped_reasons"],
        "snapshot": str(snap.name),
    }
    rep["dedup_removed"] = int(before - len(df)) if "before" in locals() else 0
    Path(f"validation_report_{year}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

def stage_build(year:int, infile:Path, outfile:Path):
    cfg_dict = load_config_dict()
    df, enc = _read_csv_with_fallback(infile)
    df = _normalize_headers(df)
    df, required, optional = _ensure_columns(df)
    df = _apply_importance_rules(df)
    df, _ = _drop_invalid_rows(df, required)
    df = df[df['date_local'].astype(str).str.startswith(f"{year}-")].copy()
    if year == 2025:
        df = df[df['date_local'] <= '2025-07-31'].copy()
    # exclusions (defensive)
    df = _apply_exclusions(df)
    # simple deduplication: date_local + title + country
    import re as _re
    def _canon_title(_s: str) -> str:
        _s = str(_s or '').strip().lower()
        _s = _s.replace('–','-').replace('—','-')
        _s = _re.sub(r'\s+', ' ', _s)
        _s = _re.sub(r'\s*([/-])\s*', r' \1 ', _s)
        return _s.strip()
    df['__dedup_key'] = (
        df['date_local'].astype(str).str[:10] + '|' +
        df['country'].astype(str).str.strip().str.upper() + '|' +
        df['title'].map(_canon_title)
    )
    df = df.drop_duplicates('__dedup_key', keep='first').drop(columns='__dedup_key')
    # end dedup
    df.reset_index(drop=True, inplace=True)
    rows = []
    official_domains = get_official_domains()
    for _, r in df.iterrows():
        tz = str(r.get("tz","")).strip()
        tz = canonicalize_tz(tz, cfg_dict)
        dt_utc_iso = _to_utc_iso(str(r["date_local"]), str(r.get("time_local","") or ""), tz or None)
        # Certainty/notes baseline
        _cert = str(r.get("certainty",""))
        _cert = _cert.strip().lower()
        _notes = str(r.get("notes",""))
        # TZ validity
        _tz_ok = bool(tz)
        if _tz_ok:
            try:
                ZoneInfo(tz)
            except Exception:
                _tz_ok = False
        if not _tz_ok:
            if _cert != 'estimated':
                _cert = 'estimated'
            if 'tz_fallback=utc' not in _notes.lower():
                _notes = (_notes + ' | tz_fallback=utc').strip(' |')
        # Domain-based promotion (official or gov-like) when tz is OK
        host = _domain_from_url(r.get('source_url',''))
        govlike_pats = get_govlike_patterns()
        alias_domains = get_alias_domains()
        canonical_map = get_canonical_host_map()
        domain_officialish = _is_officialish_host(host, official_domains, govlike_pats, alias_domains, canonical_map)
        if domain_officialish and _tz_ok and (_cert == '' or _cert == 'estimated') and str(r.get('time_local','')).strip()!='':
            _cert = 'confirmed'
        rows.append({
            "datetime_utc": dt_utc_iso,
            "event": r["title"],
            "country": r["country"],
            "impact": str(r["importance"]).strip().lower(),
            "certainty": _cert,
            "ticker": r.get("ticker",""),
            "source_url": r.get("source_url",""),
            "notes": _notes,
        })
    cols = ["datetime_utc","event","country","impact","certainty","ticker","source_url","notes"]
    out_df = pd.DataFrame(rows, columns=cols).sort_values(by=["datetime_utc","country","event"], kind="mergesort")
    csv_bytes = out_df.to_csv(index=False).encode("utf-8")
    with open(outfile, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write(csv_bytes)
    return str(outfile)

def stage_report(year:int, calendar_gz:Path, outfile:Path):
    with gzip.open(calendar_gz, "rt", encoding="utf-8") as fh:
        df = pd.read_csv(fh)

    # Prepare manual-events slice for metrics (to avoid calendar certainty=all confirmed)
    try:
        me = pd.read_csv(Path("manual_events.csv"))
        me["date_local"] = pd.to_datetime(me["date_local"], errors="coerce")
        df_me = me[(me["date_local"]>=pd.Timestamp(f"{year}-01-01")) & (me["date_local"]<=pd.Timestamp(f"{year}-12-31"))].copy()
    except Exception:
        df_me = None
    if 'datetime_utc' not in df.columns and 'dt_utc' in df.columns:
        df = df.rename(columns={'dt_utc':'datetime_utc'})
    total = len(df)
    lines = []
    lines.append(f"# Year Report — {year}\n")
    lines.append(f"_Generated at (UTC): {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}_\n")
    lines.append(f"- Total events: **{total}**\n")
    try:
        tmin = pd.to_datetime(df['datetime_utc']).min()
        tmax = pd.to_datetime(df['datetime_utc']).max()
        lines.append(f"- Date range (UTC): {tmin} → {tmax}\n")
    except Exception:
        pass
    if "country" in df.columns:
        lines.append(f"- Events by country: {df['country'].value_counts().to_dict()}\n")
    if "impact" in df.columns:
        lines.append(f"- Impact distribution: {df['impact'].value_counts().to_dict()}\n")
    # Authenticity policy (union: official_domains ∪ gov_like_patterns; no bypass for 'confirmed')
    official_domains = get_official_domains()
    govlike_pats = get_govlike_patterns()
    def _is_official_row(row):
        cert = str(row.get('certainty','')).strip().lower()
        if cert == 'secondary':
            return False
        host = _domain_from_url(row.get('source_url',''))
        alias_domains = get_alias_domains()
        canonical_map = get_canonical_host_map()
        domain_official = _is_officialish_host(host, official_domains, govlike_pats, alias_domains, canonical_map)
        return bool(domain_official)
    authentic = int(df.apply(_is_official_row, axis=1).sum()) if total else 0
    authenticity_pct = (authentic / total * 100) if total else 0.0
    lines.append(f"- Authenticity (official sources): **{authenticity_pct:.1f}%** ({authentic}/{total})\n")

    # Breakdown by source type: CB vs Statistical vs Other
    official_domains = get_official_domains()
    gov_like = get_govlike_patterns()
    def _src_bucket(row):
        host = _domain_from_url(row.get('source_url',''))
        if _is_officialish_host(host, None, gov_like):
            return 'CB'
        if _is_officialish_host(host, official_domains, []):
            return 'STAT'
        return 'OTHER'
    if not df.empty:
        buckets = df.apply(_src_bucket, axis=1).value_counts(dropna=False).to_dict()
        total_b = int(len(df))
        cb = int(buckets.get('CB', 0))
        st = int(buckets.get('STAT', 0))
        ot = int(buckets.get('OTHER', 0))
        cb_pct = (cb/total_b*100) if total_b else 0.0
        st_pct = (st/total_b*100) if total_b else 0.0
        ot_pct = (ot/total_b*100) if total_b else 0.0
        lines.append(f"- Source breakdown: CB **{cb_pct:.1f}%** ({cb}/{total_b}), STAT **{st_pct:.1f}%** ({st}/{total_b}), Other **{ot_pct:.1f}%** ({ot}/{total_b})\n")
        # Timing (exact time = not estimated/secondary)
    cert_series = (df['certainty'].fillna('').astype(str).str.lower() if 'certainty' in df.columns 
    else pd.Series(['estimated']*len(df)))
    tim_src = df_me if df_me is not None and len(df_me)>0 else df
    total_t = len(tim_src)
    cert_series = (tim_src['certainty'].fillna('').astype(str).str.lower() if 'certainty' in tim_src.columns else pd.Series(['estimated']*len(tim_src)))
    exact_time = int((~cert_series.isin(['estimated','secondary'])).sum()) if total_t else 0
    exact_time_pct = (exact_time/total_t*100) if total_t else 0.0
    w_auth, w_time = get_backtest_weights()
    score = (authenticity_pct*w_auth + exact_time_pct*w_time) if total else 0.0
    lines.append(f"\n## Backtest Suitability\n- Score: **{score:.1f}/100**\n")
    lines.append("- Heuristic: ≥80 — готов к продакшн-бэктесту; 60–79 — исследовательский; <60 — требует доочистки.\n")
    # Hashes section
    try:
        s = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
        inputs_info = s.get('years', {}).get(str(year), {}).get('inputs', None)
    except Exception:
        inputs_info = None
    try:
        cal = Path(f"calendar_{year}.csv.gz"); bun = Path(f"bundle_{year}.tar.gz")
        cplist = sorted(Path('.').glob(f"checkpoint_{year}_*.tar.gz"))
        out_lines = []
        if cal.exists(): out_lines.append(f"calendar: {cal.name} — {cal.stat().st_size} bytes")
        if bun.exists(): out_lines.append(f"bundle: {bun.name} — {bun.stat().st_size} bytes")
        for cp in cplist: out_lines.append(f"checkpoint: {cp.name} — {cp.stat().st_size} bytes")
        if out_lines:
            lines.append("\n## Archives\n" + "\n".join(["- "+s for s in out_lines]) + "\n")
    except Exception:
        pass
    lines.append("\n---\n*Built by core.py (flat edition).*\n")
    outfile.write_text("".join(lines), encoding="utf-8")
    return outfile


def update_state(year:int, calendar:Path, report:Path):
    """Update state.json with per-year info and robust input signature.

    - Computes year_slice_sha256 by parsing manual_events.csv as CSV and
      filtering rows where the `date_local` column starts with f"{year}-".
      This is robust to column reordering.
    - Includes a stable hash of config.yaml (if present).
    """
    def sha256_bytes(b: bytes) -> str:
        h = hashlib.sha256(); h.update(b); return h.hexdigest()

    # Build per-year slice hash from parsed CSV
    year_slice_sha256 = ""
    try:
        manual = Path("manual_events.csv")
        if manual.exists():
            df, _enc = _read_csv_with_fallback(manual)
            df = _normalize_headers(df)
            if "date_local" in df.columns:
                mask = df["date_local"].astype(str).str.startswith(f"{year}-")
                yslice = df.loc[mask].to_csv(index=False).encode("utf-8")
                year_slice_sha256 = sha256_bytes(yslice) if len(df.loc[mask]) else ""
    except Exception:
        year_slice_sha256 = ""

    # Compute config hash (if config.yaml exists)
    try:
        cfg_path = Path("config.yaml")
        config_sha256 = sha256_file(cfg_path) if cfg_path.exists() else ""
    except Exception:
        config_sha256 = ""

    # Persist to state.json
    data = {}
    if STATE.exists():
        try:
            data = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    years = data.get("years", {})
    years[str(year)] = {
        "calendar": calendar.name,
        "report": report.name,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {"year_slice_sha256": year_slice_sha256, "config_sha256": config_sha256}
    }
    data["years"] = years
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _file_info(p: Path):
    if not p.exists():
        return None
    return {"name": p.name, "size": p.stat().st_size, "sha256": sha256_file(p)}

def write_manifest(year:int, files:list[Path]):
    items = []
    for p in files:
        info = _file_info(p)
        if info: items.append(info)
    manifest = {"year": year, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": items}
    out = Path(f"manifest_{year}.json")
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

# --- CLI ---
def cmd_assemble(args):
    year = args.year
    providers = args.providers or ["fomc"]
    providers = (PROVIDERS_ALL if (len(providers)==1 and providers[0].lower()=="all") else providers)
    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    master = Path(args.infile) if args.infile else Path("manual_events.csv")
    stage_collect(year, providers, master, cache_dir)
    if args.dry_run:
        print(f"[dry-run] year={year} providers={providers}")
        return
    cmd_run(argparse.Namespace(year=year, infile=str(master), bundle=args.bundle, force=args.force))

def cmd_run(args):
    year = args.year
    infile = Path(args.infile) if args.infile else Path("manual_events.csv")
    if not infile.exists():
        raise SystemExit(f"Input CSV not found: {infile}")
    calendar = Path(f"calendar_{year}.csv.gz")
    report = Path(f"year_report_{year}.md")
    stage_validate(year, infile)
    stage_build(year, infile, calendar)
    update_state(year, calendar, report)
    stage_report(year, calendar, report)
    write_manifest(year, [calendar, report, Path("state.json"), Path("config.yaml")])
    if getattr(args, "bundle", False):
        cmd_bundle(argparse.Namespace(year=year))

def cmd_validate(args):
    infile = Path(args.infile) if args.infile else Path("manual_events.csv")
    stage_validate(args.year, infile)

def cmd_build(args):
    infile = Path(args.infile) if args.infile else Path("manual_events.csv")
    outfile = Path(args.outfile) if args.outfile else Path(f"calendar_{args.year}.csv.gz")
    stage_build(args.year, infile, outfile)

def cmd_report(args):
    cal = Path(args.calendar)
    out = Path(args.outfile) if args.outfile else Path(f"year_report_{args.year}.md")
    stage_report(args.year, cal, out)

def cmd_bundle(args):
    year = args.year
    man = write_manifest(year, [Path(f"calendar_{year}.csv.gz"),
                                Path(f"year_report_{year}.md"),
                                Path("state.json"),
                                Path("config.yaml")])
    import io
    mem = io.BytesIO()
    with tarfile.open(fileobj=mem, mode="w") as tf:
        def _repro(ti: tarfile.TarInfo):
            ti.uid = 0; ti.gid = 0; ti.uname = ""; ti.gname = ""; ti.mtime = 0; ti.mode = 0o644
            return ti
        for name in [f"calendar_{year}.csv.gz", f"year_report_{year}.md", f"manifest_{year}.json", "state.json", "config.yaml"]:
            p = Path(name)
            if p.exists():
                tf.add(p, arcname=p.name, filter=_repro)
    mem.seek(0)
    bundle = Path(f"bundle_{year}.tar.gz")
    with open(bundle, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write(mem.getvalue())
    print(bundle)

def main():
    ap = argparse.ArgumentParser(prog="core", description="Flat economic-calendar pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_as = sub.add_parser("assemble", help="collect -> run (validate/build/report)")
    ap_as.add_argument("--year", type=int, required=True)
    ap_as.add_argument("--providers", nargs="*", required=False, help="providers or `all`")
    ap_as.add_argument("--cache-dir", required=False)
    ap_as.add_argument("--infile", required=False, help="manual_events.csv (default: ./manual_events.csv)")
    ap_as.add_argument("--force", action="store_true")
    ap_as.add_argument("--bundle", action="store_true")
    ap_as.add_argument("--dry-run", action="store_true")
    ap_as.set_defaults(func=cmd_assemble)

    ap_run = sub.add_parser("run", help="validate -> build -> report [--bundle]")
    ap_run.add_argument("--year", type=int, required=True)
    ap_run.add_argument("--infile", required=False, help="manual_events.csv (default: ./manual_events.csv)")
    ap_run.add_argument("--force", action="store_true")
    ap_run.add_argument("--bundle", action="store_true")
    ap_run.set_defaults(func=cmd_run)

    ap_v = sub.add_parser("validate", help="validate input CSV")
    ap_v.add_argument("--year", type=int, required=True)
    ap_v.add_argument("--infile", required=False)
    ap_v.set_defaults(func=cmd_validate)

    ap_b = sub.add_parser("build", help="build calendar CSV.GZ")
    ap_b.add_argument("--year", type=int, required=True)
    ap_b.add_argument("--infile", required=False)
    ap_b.add_argument("--outfile", required=False)
    ap_b.set_defaults(func=cmd_build)

    ap_r = sub.add_parser("report", help="write year report")
    ap_r.add_argument("--year", type=int, required=True)
    ap_r.add_argument("--calendar", required=True)
    ap_r.add_argument("--outfile", required=False)
    ap_r.set_defaults(func=cmd_report)

    ap_bd = sub.add_parser("bundle", help="zip outputs for a given year")
    ap_bd.add_argument("--year", type=int, required=True)
    ap_bd.set_defaults(func=cmd_bundle)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()