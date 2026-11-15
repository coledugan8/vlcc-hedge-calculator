"""Fetch the latest market data from FRED and write data/data.json for the website.

Runs daily in GitHub Actions (see .github/workflows/update-data.yml). Standard library only.

Series (all free, no API key needed):
  PCU483111483111  U.S. PPI, Deep Sea Freight Transportation (BLS via FRED), monthly index
                   -> used as a free PROXY for VLCC earnings (not VLCC-specific)
  MCOILBRENTEU     Brent crude spot, monthly average, $/bbl (EIA via FRED)
  MCOILWTICO       WTI crude spot, monthly average, $/bbl (EIA via FRED)
  DCOILBRENTEU     Brent crude spot, daily, $/bbl (latest value only, for the "market now" strip)
  DCOILWTICO       WTI crude spot, daily, $/bbl (latest value only)
"""
import csv, io, json, os, sys, time, datetime, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "data.json")
CONFIG = os.path.join(ROOT, "config.json")
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"


FRED_API = ("https://api.stlouisfed.org/fred/series/observations"
            "?series_id={sid}&api_key={key}&file_type=json&observation_start={start}")


def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (vlcc-hedge-calculator; +https://github.com)",
        "Accept": "text/csv,application/json,*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def fetch_series(sid, start, tries=3):
    """Return {YYYY-MM-DD: float} for a FRED series, skipping missing values ('.').

    Uses the official FRED API when the FRED_API_KEY secret is set (most reliable),
    otherwise the public CSV download.
    """
    key = os.environ.get("FRED_API_KEY", "").strip()
    last_err = None
    for attempt in range(tries):
        try:
            if key:
                js = json.loads(_get(FRED_API.format(sid=sid, key=key, start=start)))
                if "observations" not in js:
                    raise RuntimeError(js.get("error_message", "unexpected FRED API response"))
                out = {}
                for o in js["observations"]:
                    try:
                        out[o["date"]] = float(o["value"])
                    except ValueError:
                        pass
                return out
            return parse_fred_csv(_get(FRED_CSV.format(sid=sid, start=start)), sid)
        except Exception as e:  # network hiccup: wait and retry
            last_err = e
            print(f"  {sid}: attempt {attempt + 1} failed: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Could not download {sid}: {last_err}")


def parse_fred_csv(text, sid):
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        raise ValueError(f"{sid}: empty response")
    header = rows[0]
    col = header.index(sid) if sid in header else 1  # first column is the date (DATE or observation_date)
    out = {}
    for row in rows[1:]:
        if len(row) <= col:
            continue
        try:
            out[row[0][:10]] = float(row[col])
        except ValueError:
            pass  # '.' = missing observation
    return out


def monthly(d):
    return {k[:7]: v for k, v in d.items()}


def latest(d):
    if not d:
        return None
    k = max(d)
    return {"date": k, "value": round(d[k], 2)}


def main():
    cfg = {"start": "2015-01", "freight_series": "PCU483111483111", "anchor_tce": 40000}
    if os.path.exists(CONFIG):
        with open(CONFIG) as f:
            cfg.update(json.load(f))
    start = cfg["start"] + "-01"
    recent = (datetime.date.today() - datetime.timedelta(days=45)).isoformat()

    freight = monthly(fetch_series(cfg["freight_series"], start))
    brent = monthly(fetch_series("MCOILBRENTEU", start))
    wti = monthly(fetch_series("MCOILWTICO", start))
    brent_d = fetch_series("DCOILBRENTEU", recent)
    wti_d = fetch_series("DCOILWTICO", recent)

    months = sorted(set(freight) & set(brent) & set(wti))
    if len(months) < 60:
        raise RuntimeError(f"Only {len(months)} complete months - refusing to overwrite the data file.")
    rows = [[m, round(freight[m], 3), round(brent[m], 2), round(wti[m], 2)] for m in months]

    payload = {
        "monthly_columns": ["month", "freight_index", "brent", "wti"],
        "monthly": rows,
        "daily": {"brent": latest(brent_d), "wti": latest(wti_d)},
        "latest_available": {
            "freight_index": max(freight) if freight else None,
            "brent": max(brent) if brent else None,
            "wti": max(wti) if wti else None,
        },
        "anchor_tce": cfg["anchor_tce"],
        "sources": {
            "freight_index": f"FRED {cfg['freight_series']} (U.S. BLS Producer Price Index, Deep Sea Freight Transportation)",
            "brent": "FRED MCOILBRENTEU / DCOILBRENTEU (U.S. EIA Europe Brent spot)",
            "wti": "FRED MCOILWTICO / DCOILWTICO (U.S. EIA Cushing WTI spot)",
        },
    }

    old = None
    if os.path.exists(OUT):
        with open(OUT) as f:
            try:
                old = json.load(f)
            except ValueError:
                old = None
    if old and {k: v for k, v in old.items() if k != "updated"} == payload:
        print("No new data; data.json unchanged.")
        return
    payload["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"Wrote {len(rows)} months ({rows[0][0]} to {rows[-1][0]}); daily Brent {payload['daily']['brent']}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Update failed: {e}", file=sys.stderr)
        sys.exit(1)
