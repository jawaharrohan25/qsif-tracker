import json, re, sys, os, html as H, datetime, urllib.request

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


AAA_ROW = r"qsif Active Asset Allocator Long-Short Fund\s*-\s*Growth Option\s*-\s*Direct Plan"

FUNDS = {
    "equity": [(SW + "qsif-equity-long-short-fund-direct-growth", parse_stackwealth)],
    "hybrid": [(SW + "qsif-hybrid-long-short-fund-direct-growth", parse_stackwealth)],
    "aaa": [(QSIF, qsif_row(AAA_ROW)),
            (SW + "qsif-active-asset-allocator-long-short-fund-direct-growth", parse_stackwealth)],
}


def fetch(url):
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
        data = json.load(open(path, encoding="utf-8"))
        if isinstance(data, list):
            data = {"equity": data}
    missing = []
    for fid, sources in FUNDS.items():
        rows = data.get(fid, [])
        got = latest_reading(sources, getter)
        if not got:
            print(fid, ": no reading")
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


if __name__ == "__main__":
    sys.exit(1 if run(fetch) else 0)
