from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import urlencode, parse_qsl
import ssl, json, re

REVAL = "https://pun.unipune.ac.in"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def _fetch(method, path, data=None, cj=None):
    url = f"{REVAL}{path}"
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": f"{REVAL}/revalresult/"}
    if cj and "ASP.NET_SessionId" in cj:
        h["Cookie"] = f"ASP.NET_SessionId={cj['ASP.NET_SessionId']}"
    if data:
        body = urlencode(data).encode()
        req = Request(url, data=body, headers={**h, "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    else:
        req = Request(url, headers=h, method=method)
    resp = urlopen(req, context=ctx, timeout=20)
    html = resp.read().decode("utf-8", errors="replace")
    sc = resp.headers.get("Set-Cookie", "")
    sid = ""
    if sc:
        m = re.search(r"ASP.NET_SessionId=([^;]+)", sc)
        if m: sid = m.group(1)
    return html, sid

def _vs(html):
    vs = re.search(r'__VIEWSTATE[^>]*value="([^"]*)"', html)
    ev = re.search(r'__EVENTVALIDATION[^>]*value="([^"]*)"', html)
    vsg = re.search(r'__VIEWSTATEGENERATOR[^>]*value="([^"]*)"', html)
    return (vs.group(1) if vs else "", ev.group(1) if ev else "", vsg.group(1) if vsg else "")

def _action(html):
    m = re.search(r'<form[^>]*action="([^"]*)"', html, re.DOTALL)
    if m:
        a = m.group(1)
        if a in ('', '.'): return '/revalresult/'
        if a.startswith('./'): return '/revalresult/' + a[1:]
        if a.startswith('/'): return a
        return '/revalresult/' + a
    return '/revalresult/'

def _courses(html):
    courses = []
    m = re.search(r'<table[^>]*id="grdColleges"[^>]*>(.*?)</table>', html, re.DOTALL)
    if not m: return courses
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', m.group(1), re.DOTALL)
    for row in rows:
        if "HeaderStyle" in row or "PagerStyle" in row or "FooterStyle" in row: continue
        if "GridViewFooterStyle" in row: continue
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 3: continue
        course = re.sub(r'<[^>]+>', "", cells[0]).strip()
        subject = re.sub(r'<[^>]+>', "", cells[1]).strip()
        if not course or not subject: continue
        if course in ("...", "&hellip;", ""): continue
        etm = re.search(r"__doPostBack\(&#39;([^&#]+?)&#39;", cells[2])
        if not etm: continue
        courses.append({"course": course, "subject": subject, "event_target": etm.group(1)})
    return courses

def _pager_links(html):
    links = []
    for m in re.finditer(r"__doPostBack\(&#39;(.+?)&#39;,\s*&#39;(.+?)&#39;", html):
        target = m.group(1)
        arg = m.group(2)
        pm = re.search(r"Page\$(\d+)", arg)
        if pm:
            links.append((int(pm.group(1)), target, arg))
    return links

MAX_REVAL_PAGES = 50

def scrape_courses():
    html, sid = _fetch("GET", "/revalresult/")
    cj = {"ASP.NET_SessionId": sid} if sid else {}
    all_courses = _courses(html)
    seen = {(c["course"], c["subject"], c["event_target"]) for c in all_courses}
    vs, ev, vsg = _vs(html)
    current_page = 1
    for _ in range(MAX_REVAL_PAGES):
        pager = _pager_links(html)
        next_page = None
        next_target = ""
        next_arg = ""
        for pn, t, a in pager:
            if pn > current_page and (next_page is None or pn < next_page):
                next_page = pn
                next_target = t
                next_arg = a
        if next_page is None:
            break
        fd = {"__VIEWSTATE": vs, "__EVENTVALIDATION": ev, "__VIEWSTATEGENERATOR": vsg, "__EVENTTARGET": next_target, "__EVENTARGUMENT": next_arg}
        h, sid = _fetch("POST", "/revalresult/", fd, cj)
        if not h:
            break
        if sid:
            cj["ASP.NET_SessionId"] = sid
        vs, ev, vsg = _vs(h)
        for c in _courses(h):
            key = (c["course"], c["subject"], c["event_target"])
            if key not in seen:
                seen.add(key)
                all_courses.append(c)
        current_page = next_page
        html = h
    return all_courses

def _extract_exam_val(html):
    m = re.search(r'id="cboExamName"[^>]*>.*?<option[^>]*selected[^>]*value="([^"]*)"', html, re.DOTALL)
    if m: return m.group(1)
    m = re.search(r'id="cboExamName"[^>]*>.*?<option[^>]*value="([^"]*)"', html, re.DOTALL)
    return m.group(1) if m else ""

def _extract_result(html):
    cleaned = re.sub(r'<script[^>]*>[\s\S]*?</script>|<style[^>]*>[\s\S]*?</style>|<link[^>]*>', '', html, flags=re.DOTALL)
    cleaned = re.sub(r'<input[^>]*type="hidden"[^>]*>', '', cleaned)
    cleaned = re.sub(r'<img[^>]*>', '', cleaned)
    cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)

    tables = re.finditer(r'(<table[^>]*>(?:(?!</table>)[\s\S])*?</table>)', cleaned, re.DOTALL | re.IGNORECASE)
    candidates = []
    for t in tables:
        tc = t.group(1)
        if re.search(r'SubCode|SubName|Obt[^a-z]|Chng[^a-z]|Remarks', tc, re.IGNORECASE):
            candidates.append(tc)

    if candidates:
        best = max(candidates, key=len)
        idx = cleaned.find(best)
        before = cleaned[max(0, idx-800):idx]
        student_info = ''
        si_m = re.search(r'(Seat\s*(?:No|Number)[^<]*(?:<[^>]*>)*[^<]*?(?:S\d[\d/]*[A-Z]?)?)', before, re.DOTALL | re.IGNORECASE)
        if si_m: student_info = re.sub(r'<[^>]+>', '', si_m.group(1)).strip()
        nm_m = re.search(r'(Name[^<]*(?:<[^>]*>)*[^<]*?[A-Z][a-zA-Z\s]+)', before, re.DOTALL | re.IGNORECASE)
        if nm_m: student_info += '<br>' + re.sub(r'<[^>]+>', '', nm_m.group(1)).strip()
        prn_m = re.search(r'(PRN[^<]*(?:<[^>]*>)*[^<]*?(?:\d+[A-Z]?)?)', before, re.DOTALL | re.IGNORECASE)
        if prn_m: student_info += '<br>' + re.sub(r'<[^>]+>', '', prn_m.group(1)).strip()
        wrap = '<div class="reval-result">'
        if student_info:
            wrap += '<div class="rv-student-info">' + student_info.strip() + '</div>'
        wrap += best + '</div>'
        return wrap

    for pat in [
        r'<td[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</td>',
        r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
        r'<td[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)</td>',
        r'<div[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)</div>',
    ]:
        m = re.search(pat, cleaned, re.DOTALL | re.IGNORECASE)
        if m:
            inner = m.group(1).strip()
            if len(inner) > 100:
                return '<div class="reval-result">' + inner + '</div>'
    return None


def _result_link(html):
    m = re.search(r"__doPostBack\(&#39;(grdColleges\$ctl\d+\$LinkButton1)&#39;", html)
    return m.group(1) if m else None

def search_result(event_target, search_by, search_value):
    html, sid = _fetch("GET", "/revalresult/")
    cj = {"ASP.NET_SessionId": sid} if sid else {}
    vs, ev, vsg = _vs(html)
    fd = {"__VIEWSTATE": vs, "__EVENTVALIDATION": ev, "__VIEWSTATEGENERATOR": vsg, "__EVENTTARGET": event_target, "__EVENTARGUMENT": ""}
    h, sid = _fetch("POST", "/revalresult/", fd, cj)
    if sid: cj["ASP.NET_SessionId"] = sid
    vs, ev, vsg = _vs(h)
    path = _action(h)
    exam_val = _extract_exam_val(h)
    fd2 = {"__VIEWSTATE": vs, "__EVENTVALIDATION": ev, "__VIEWSTATEGENERATOR": vsg, "__EVENTTARGET": "", "__EVENTARGUMENT": "", "cboExamName": exam_val, "cboSearchBy": search_by, "txtSearch": search_value, "btnShow": "Submit"}
    rh, _ = _fetch("POST", path, fd2, cj)
    # Check if we got a student list with "Result" link instead of actual result
    rl = _result_link(rh)
    if rl:
        vs3, ev3, vsg3 = _vs(rh)
        path3 = _action(rh)
        fd3 = {"__VIEWSTATE": vs3, "__EVENTVALIDATION": ev3, "__VIEWSTATEGENERATOR": vsg3, "__EVENTTARGET": rl, "__EVENTARGUMENT": ""}
        rh, _ = _fetch("POST", path3, fd3, cj)
    extracted = _extract_result(rh)
    if extracted:
        return {"html": extracted}
    body_m = re.search(r'<body[^>]*>([\s\S]*)</body>', rh, re.DOTALL)
    if body_m:
        inner = re.sub(r'<script[^>]*>[\s\S]*?</script>|<style[^>]*>[\s\S]*?</style>', "", body_m.group(1), flags=re.DOTALL)
        inner = inner.strip()
        if len(inner) > 100: return {"html": inner}
    return {"html": rh}

def _send_json(self, data, status=200):
    self.send_response(status)
    self.send_header("Content-Type", "application/json")
    self.send_header("Access-Control-Allow-Origin", "*")
    self.end_headers()
    self.wfile.write(json.dumps(data).encode())

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Requested-With")
        self.end_headers()

    def do_GET(self):
        try:
            data = scrape_courses()
            _send_json(self, data)
        except Exception as e:
            _send_json(self, {"error": str(e)}, 500)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""
            post = dict(parse_qsl(body))
            event_target = post.get("event_target", "")
            search_by = post.get("search_by", "Seat No")
            search_value = post.get("search_value", "")
            if not event_target or not search_value:
                _send_json(self, {"error": "Missing event_target or search_value"}, 400)
                return
            data = search_result(event_target, search_by, search_value)
            _send_json(self, data)
        except Exception as e:
            _send_json(self, {"error": str(e)}, 500)
