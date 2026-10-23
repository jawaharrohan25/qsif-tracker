import json, re, sys, os, html as H, datetime, urllib.request, urllib.parse, http.cookiejar

OUT = "nav.json"
UA = {"User-Agent": "Mozilla/5.0"}
MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
SW = "https://stackwealth.in/mutual-funds/"
QSIF = "https://www.qsif.com/NAV/latestnav"


def plain(page):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", H.unescape(s))


def parse_stackwealth(page):
    t = plain(page)
    m = re.search(r"Net Asset Value \(NAV\) of [^.]*? as of \w{3} (\w{3}) (\d{1,2}) (\d{4}) is\s*₹\s*([0-9]+\.[0-9]+)", t)
    if m:
        return "%s-%02d-%02d" % (m.group(3), MON[m.group(1)], int(m.group(2))), float(m.group(4))
    m = re.search(r"NAV on (\d{4}-\d{2}-\d{2})\s*₹\s*([0-9]+\.[0-9]+)", t)
    if m:
        return m.group(1), float(m.group(2))
    return None


def qsif_row(name):
    pat = r"(\d{2})-([A-Za-z]{3})-(\d{4})\s+" + name + r"\s+Growth\s+([0-9]+\.[0-9]+)"

    def parse(page):
        m = re.search(pat, plain(page), flags=re.I)
        if not m:
            return None
        return "%s-%02d-%02d" % (m.group(3), MON[m.group(2).title()], int(m.group(1))), float(m.group(4))
    return parse


ROW = re.compile(r"(\d{2})-([A-Za-z]{3})-(\d{4})\s+(qsif .*?)\s+(Growth|Dividend)\s+([0-9]+\.[0-9]+)", re.I)


def qsif_direct_growth(keyword, avoid=("ex-top", "sector", "idcw", "dividend")):
    """Newest Direct-plan Growth row whose scheme name contains `keyword` (anywhere in the qsif.com NAV table)."""
    def parse(page):
        best = None
        for m in ROW.finditer(plain(page)):
            name = m.group(4).lower()
            if keyword not in name or "direct" not in name or m.group(5).lower() != "growth":
                continue
            if any(a in name for a in avoid):
                continue
            d = "%s-%02d-%02d" % (m.group(3), MON[m.group(2).title()], int(m.group(1)))
            if best is None or d > best[0]:
                best = (d, float(m.group(6)))
        return best
    return parse


AAA_ROW = r"qsif Active Asset Allocator Long-Short Fund\s*-\s*Growth Option\s*-\s*Direct Plan"

def scheme(name):
    """Row matcher for a scheme name exactly as qsif.com prints it, e.g. "qsif Equity Long-Short Fund - Direct - Growth".
    Hyphens may have spaces around them or none, and spaces may be any whitespace."""
    parts = [re.sub(r"(\\ )+", r"\\s+", re.escape(x)) for x in re.split(r"\s*-\s*", name.strip())]
    return qsif_row(r"\s*-\s*".join(parts))


FUNDS = {
    "equity": [(QSIF, scheme("qsif Equity Long-Short Fund - Direct - Growth"))],
    "hybrid": [(QSIF, scheme("qsif Hybrid Long-Short Fund - Direct - Growth"))],
    "aaa": [(QSIF, qsif_row(AAA_ROW))],
    "ex100": [(QSIF, scheme("qsif Equity Ex-Top 100 Long-Short Fund - Direct - Growth"))],
}


# A fund listed here can be absent from qsif.com (for example before its Direct plan is published) without failing the job.
OPTIONAL = {"ex100"}


def _read(opener, req):
    return opener.open(req, timeout=30).read().decode("utf-8", "ignore")


def fetch_qsif(url=QSIF, opener=None):
    """The qsif.com NAV table is an ASP.NET grid with pages. Fetch page 1, then ask for every other numbered
    page the same way a browser does (a form post with the hidden fields and the page link's event target).
    Returns all the pages joined together so the row parsers can look through them."""
    if opener is None:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    first = _read(opener, urllib.request.Request(url, headers=UA))
    pages = [first]
    hidden = {}
    for tag in re.findall(r"<input[^>]*>", first, flags=re.I):
        if re.search(r'type=["\']?hidden', tag, flags=re.I):
            n = re.search(r'name=["\']([^"\']+)', tag)
            v = re.search(r'value=["\']([^"\']*)', tag)
            if n:
                hidden[n.group(1)] = H.unescape(v.group(1)) if v else ""
    targets = []
    for m in re.finditer(r"__doPostBack\((?:'|&#39;|&quot;)([^'&\"]+)(?:'|&#39;|&quot;)\s*,[^>]*>\s*(\d+)\s*</a>", first, flags=re.I):
        if m.group(2) != "1" and m.group(1) not in targets:
            targets.append(m.group(1))
    if not targets:
        targets = ["ctl00$ContentPlaceHolder1$nav_sch$ctl01$ctl01"]  # the page 2 link seen on qsif.com
    for t in targets[:5]:
        try:
            form = dict(hidden); form["__EVENTTARGET"] = t; form["__EVENTARGUMENT"] = ""
            req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(), headers=dict(UA, **{"Content-Type": "application/x-www-form-urlencoded", "Referer": url}))
            pages.append(_read(opener, req))
        except Exception as e:
            print("  could not load page of the qsif.com table:", t, e)
    print("  qsif.com: read", len(pages), "page(s) of the NAV table")
    return "\n".join(pages)


def fetch(url):
    if url == QSIF:
        return fetch_qsif(url)
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


def latest_reading(sources, getter):
    best = None
    for url, parser in sources:
        try:
            got = parser(getter(url))
        except Exception as e:
            print("  source failed:", url, e)
            continue
        if not got:
            print("  nothing found at", url)
            continue
        d, n = got
        if not (0 < n < 1000) or d > (datetime.date.today() + datetime.timedelta(days=1)).isoformat():
            print("  rejected suspicious reading:", d, n, url)
            continue
        if best is None or d > best[0]:
            best = (d, n)
    return best


def run(getter, path=OUT):
    data = {}
    if os.path.exists(path):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except ValueError as e:
            print("nav.json is not valid JSON (%s). Starting a fresh one; the page keeps its built-in readings." % e)
            data = {}
        if isinstance(data, list):
            data = {"equity": data}
    missing = []
    for fid, sources in FUNDS.items():
        rows = data.get(fid, [])
        got = latest_reading(sources, getter)
        if not got:
            print(fid, ": no reading")
            if fid not in OPTIONAL:
                missing.append(fid)
        else:
            d, n = got
            rows = [r for r in rows if r["d"] != d]
            rows.append({"d": d, "n": n, "s": "daily update"})
            print(fid, ": saved", d, n)
        rows.sort(key=lambda r: r["d"])
        data[fid] = rows
    json.dump(data, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return missing


NIFTY_OUT = "nifty.json"
NIFTY_URLS = ["https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?range=2y&interval=1d",
              "https://query2.finance.yahoo.com/v8/finance/chart/%5ENSEI?range=2y&interval=1d"]


def parse_nifty(text):
    """Daily closes of the Nifty 50 from Yahoo Finance's chart data -> [{"d": "YYYY-MM-DD", "n": close}]."""
    res = json.loads(text)["chart"]["result"][0]
    off = res.get("meta", {}).get("gmtoffset", 19800)
    closes = res["indicators"]["quote"][0]["close"]
    rows = {}
    for ts, c in zip(res["timestamp"], closes):
        if c is None or not (1000 < c < 200000):
            continue
        d = (
    datetime.datetime.fromtimestamp(
        ts + off, datetime.timezone.utc
    )
    .date()
    .isoformat()
)
        rows[d] = round(float(c), 2)
    return [{"d": d, "n": rows[d]} for d in sorted(rows)]


def run_nifty(getter, path=NIFTY_OUT):
    """Optional: a failure here is reported but never fails the NAV update."""
    new = None
    for url in NIFTY_URLS:
        try:
            new = parse_nifty(getter(url))
            if new:
                break
        except Exception as e:
            print("  nifty source failed:", url, e)
    if not new:
        print("nifty : no reading")
        return False
    old = []
    if os.path.exists(path):
        try:
            old = json.load(open(path, encoding="utf-8"))
        except ValueError:
            old = []
    m = {r["d"]: r["n"] for r in old if isinstance(r, dict) and "d" in r and "n" in r}
    m.update({r["d"]: r["n"] for r in new})
    rows = [{"d": d, "n": m[d]} for d in sorted(m)]
    json.dump(rows, open(path, "w", encoding="utf-8"), indent=0)
    print("nifty : saved", len(rows), "days, latest", rows[-1]["d"], rows[-1]["n"])
    return True


def fetch_nifty_page(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


if __name__ == "__main__":
    missing = run(fetch)
    try:
        run_nifty(fetch_nifty_page)
    except Exception as e:
        print("nifty : skipped", e)
    sys.exit(1 if missing else 0)
