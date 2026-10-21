#!/usr/bin/env python3
"""Fetch official Nifty 500 Total Returns Index history from NSE Indices."""
import datetime as dt, json, os, time, urllib.request
from pathlib import Path

URL = "https://www.niftyindices.com/Backpage.aspx/getTotalReturnIndexString"
OUT = Path("nifty500tri.json")
HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Referer": "https://www.niftyindices.com/reports/historical-data",
    "Origin": "https://www.niftyindices.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01"
}

def request_chunk(start, end):
    inner = "{'name':'NIFTY 500','startDate':'%s','endDate':'%s','indexName':'NIFTY 500'}" % (start.strftime('%d-%b-%Y'), end.strftime('%d-%b-%Y'))
    body = json.dumps({"cinfo": inner}).encode()
    req = urllib.request.Request(URL, data=body, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode('utf-8', errors='replace')
            status = r.status
    except Exception as exc:
        raise RuntimeError(f"NSE TRI request failed for {start} to {end}: {exc}") from exc
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError as exc:
        sample = raw[:240].replace("\\n", " ").replace("\\r", " ")
        raise RuntimeError(
            f"NSE returned a non-JSON response for {start} to {end} (HTTP {status}). "
            f"This may be a bot-protection or endpoint response. Response starts: {sample!r}"
        ) from exc
    payload = outer.get('d', '[]')
    if isinstance(payload, str):
        if payload.lower() == 'false' or payload == '[]': return []
        payload = json.loads(payload)
    rows=[]
    for item in payload:
        date_text = item.get('Date') or item.get('HistoricalDate')
        value = item.get('TotalReturnsIndex') or item.get('Total Returns Index')
        if not date_text or not value: continue
        d = dt.datetime.strptime(date_text, '%d %b %Y').date().isoformat()
        n = float(value)
        if n > 0: rows.append({'d': d, 'n': round(n, 4)})
    return rows

def main():
    try: old = json.loads(OUT.read_text())
    except (OSError, ValueError): old = []
    oldmap = {x['d']: float(x['n']) for x in old if isinstance(x,dict) and x.get('d') and x.get('n')}
    today = dt.date.today()
    # First run imports the full available official series from 1995; later runs update from the latest saved date.
    start = dt.date(1995, 1, 1) if not oldmap else max(dt.date.fromisoformat(max(oldmap)), today - dt.timedelta(days=10))
    if start > today: start = today
    cur = start
    imported = 0
    while cur <= today:
        end = min(cur + dt.timedelta(days=364), today)
        rows = request_chunk(cur, end)
        for r in rows: oldmap[r['d']] = r['n']
        imported += len(rows)
        print(f'Nifty 500 TRI {cur} to {end}: {len(rows)} rows')
        cur = end + dt.timedelta(days=1)
        time.sleep(0.6)
    out = [{'d': d, 'n': oldmap[d]} for d in sorted(oldmap)]
    if not out: raise RuntimeError('NSE returned no Nifty 500 TRI data; refusing to overwrite existing data.')
    OUT.write_text(json.dumps(out, indent=0) + '\n', encoding='utf-8')
    print(f'Saved {len(out)} official Nifty 500 TRI observations; imported/updated {imported}; latest={out[-1]}')

if __name__ == '__main__': main()
