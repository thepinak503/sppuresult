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

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Requested-With")
        self.end_headers()

    def do_GET(self):
        try:
            req = Request(f"{SPPU}/Result/Dashboard/Default", headers=_headers(self))
            resp = urlopen(req, context=ctx)
            html = resp.read().decode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            sc = resp.headers.get("Set-Cookie")
            if sc: self.send_header("Set-Cookie", sc.split(";")[0])
            self.end_headers()
            self.wfile.write(json.dumps({"html": html}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
