from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen
import ssl, json

SPPU = "https://onlineresults.unipune.ac.in"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def _headers(self):
    h = {"User-Agent": "Mozilla/5.0", "Referer": f"{SPPU}/Result/Dashboard/Default", "X-Requested-With": "XMLHttpRequest"}
    c = self.headers.get("Cookie", "")
    if c: h["Cookie"] = c
    return h

def _send_json(self, status, data):
    self.send_response(status)
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Content-Type", "application/json")
    self.end_headers()
    self.wfile.write(json.dumps(data).encode())

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Requested-With")
        self.end_headers()

    def do_POST(self):
        try:
            req = Request(f"{SPPU}/Result/Dashboard/RFCTLN", method="POST", headers=_headers(self))
            resp = urlopen(req, context=ctx)
            body = resp.read().decode()
            sc = resp.headers.get("Set-Cookie")
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            if sc: self.send_header("Set-Cookie", sc.split(";")[0])
            self.end_headers()
            self.wfile.write(body.encode())
        except Exception as e:
            _send_json(self, 500, {"error": str(e)})
