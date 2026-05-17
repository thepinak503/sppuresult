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

def _courses(html):
    courses = []
    m = re.search(r'<table[^>]*id="grdColleges"[^>]*>(.*?)</table>', html, re.DOTALL)
    if not m: return courses
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', m.group(1), re.DOTALL)
    for row in rows:
        if "HeaderStyle" in row or "PagerStyle" in row or "FooterStyle" in row: continue
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 3: continue
        course = re.sub(r'<[^>]+>', "", cells[0]).strip()
        subject = re.sub(r'<[^>]+>', "", cells[1]).strip()
        etm = re.search(r"__doPostBack\(&#39;([^&#]+?)&#39;", cells[2])
        courses.append({"course": course, "subject": subject, "event_target": etm.group(1) if etm else ""})
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

def scrape_courses():
    html, sid = _fetch("GET", "/revalresult/")
    cj = {"ASP.NET_SessionId": sid} if sid else {}
    all_courses = _courses(html)
    seen = {(c["course"], c["subject"], c["event_target"]) for c in all_courses}
    vs, ev, vsg = _vs(html)
    current_page = 1
    for _ in range(100):
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

def search_result(event_target, search_by, search_value):
    html, sid = _fetch("GET", "/revalresult/")
    cj = {"ASP.NET_SessionId": sid} if sid else {}
    vs, ev, vsg = _vs(html)
    fd = {"__VIEWSTATE": vs, "__EVENTVALIDATION": ev, "__VIEWSTATEGENERATOR": vsg, "__EVENTTARGET": event_target, "__EVENTARGUMENT": ""}
    h, sid = _fetch("POST", "/revalresult/", fd, cj)
    if sid: cj["ASP.NET_SessionId"] = sid
    vs, ev, vsg = _vs(h)
    exam_m = re.search(r'id="cboExamName"[^>]*>.*?<option[^>]*selected[^>]*value="([^"]*)"', h, re.DOTALL)
    exam_val = exam_m.group(1) if exam_m else ""
    fd2 = {"__VIEWSTATE": vs, "__EVENTVALIDATION": ev, "__VIEWSTATEGENERATOR": vsg, "__EVENTTARGET": "", "__EVENTARGUMENT": "", "cboExamName": exam_val, "cboSearchBy": search_by, "txtSearch": search_value, "btnShow": "Submit"}
    rh, _ = _fetch("POST", "/revalresult/", fd2, cj)
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
