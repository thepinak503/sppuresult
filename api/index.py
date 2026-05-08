from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import parse_qs
import ssl, json

SPPU = "https://onlineresults.unipune.ac.in"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def _fetch(url, data=None, headers=None, method=None):
    req = Request(url, data=data, headers=headers or {}, method=method or ("POST" if data else "GET"))
    return urlopen(req, context=ctx)

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self._cors()
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if "sessions" in self.path:
            self._proxy("GET", f"{SPPU}/Result/Dashboard/GetSession")
        elif "courses" in self.path:
            qs = parse_qs(self.path.split("?")[1]) if "?" in self.path else {}
            period = qs.get("period", [""])[0]
            target = f"{SPPU}/Result/Dashboard/Default"
            if period: target += f"?Exam_Period={period}"
            self._proxy("GET", target)
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        if "captcha" in self.path:
            self._proxy("POST", f"{SPPU}/Result/Dashboard/RFCTLN")
        elif "result" in self.path:
            self._result()
        else:
            self._json(404, {"error": "Not found"})

    def _proxy(self, method, url):
        try:
            resp = _fetch(url, headers=self._headers(), method=method)
            body = resp.read()
            self._cors()
            if method == "POST" or "sessions" in self.path:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                sc = resp.headers.get("Set-Cookie")
                if sc: self.send_header("Set-Cookie", sc.split(";")[0])
                self.end_headers()
                self.wfile.write(body)
            else:
                html = body.decode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                sc = resp.headers.get("Set-Cookie")
                if sc: self.send_header("Set-Cookie", sc.split(";")[0])
                self.end_headers()
                self.wfile.write(json.dumps({"html": html}).encode())
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _result(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            resp = _fetch(
                f"{SPPU}/SPPU%20ONLINE%20RESULT%20DISPLAY",
                data=body,
                headers={**self._headers(), "Content-Type": "application/x-www-form-urlencoded"},
            )
            pdf = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", resp.headers.get("Content-Type", "application/pdf"))
            cd = resp.headers.get("Content-Disposition", "")
            if cd: self.send_header("Content-Disposition", cd)
            sc = resp.headers.get("Set-Cookie")
            if sc: self.send_header("Set-Cookie", sc.split(";")[0])
            self._cors()
            self.end_headers()
            self.wfile.write(pdf)
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _headers(self):
        h = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": f"{SPPU}/Result/Dashboard/Default",
            "X-Requested-With": "XMLHttpRequest",
        }
        c = self.headers.get("Cookie", "")
        if c: h["Cookie"] = c
        return h

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Requested-With")

    def _json(self, status, data):
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
