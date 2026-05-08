#!/usr/bin/env python3
"""
SPPU Result Proxy Server
Run: python3 server.py
Then open: http://localhost:8080
"""
import http.server
import urllib.request
import urllib.parse
import json
import ssl
import os
import sys
import traceback

SPPU_BASE = "https://onlineresults.unipune.ac.in"
PORT = int(os.environ.get("PORT", 8080))

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

class SPPUSession:
    def __init__(self):
        self.cookies = {}
        self._init_session()

    def _init_session(self):
        try:
            req = urllib.request.Request(
                f"{SPPU_BASE}/Result/Dashboard/Default",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
            )
            resp = urllib.request.urlopen(req, context=ssl_ctx, timeout=10)
            for c in resp.headers.get_all("Set-Cookie") or []:
                name = c.split("=")[0].strip()
                val = c.split(";")[0].split("=", 1)[1] if "=" in c.split(";")[0] else ""
                self.cookies[name] = val
        except:
            pass

    def _cookie_header(self):
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def _update_cookies(self, resp):
        for c in resp.headers.get_all("Set-Cookie") or []:
            try:
                name_val = c.split(";")[0]
                if "=" in name_val:
                    name, val = name_val.split("=", 1)
                    self.cookies[name.strip()] = val.strip()
            except:
                pass

    def post_json(self, path, data=None):
        try:
            url = f"{SPPU_BASE}{urllib.parse.quote(path, safe='/')}"
            body = urllib.parse.urlencode(data or {}).encode()
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            req.add_header("X-Requested-With", "XMLHttpRequest")
            req.add_header("Referer", f"{SPPU_BASE}/Result/Dashboard/Default")
            req.add_header("Cookie", self._cookie_header())
            resp = urllib.request.urlopen(req, context=ssl_ctx, timeout=15)
            self._update_cookies(resp)
            content = resp.read().decode("utf-8", errors="replace").strip()
            if content.startswith(("{", "[")):
                return json.loads(content)
            return {"raw": content[:1000]}
        except urllib.error.HTTPError as e:
            try:
                c = e.read().decode("utf-8", errors="replace").strip()
                if c.startswith(("{", "[")):
                    return json.loads(c)
                return {"error": str(e), "status": e.code, "body": c[:500]}
            except:
                return {"error": str(e), "status": e.code}
        except Exception as e:
            return {"error": str(e)}

    def get_text(self, path, params=None):
        try:
            url = f"{SPPU_BASE}{urllib.parse.quote(path, safe='/')}"
            if params:
                url += "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
            req.add_header("X-Requested-With", "XMLHttpRequest")
            req.add_header("Referer", f"{SPPU_BASE}/Result/Dashboard/Default")
            req.add_header("Cookie", self._cookie_header())
            resp = urllib.request.urlopen(req, context=ssl_ctx, timeout=15)
            self._update_cookies(resp)
            return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return f"<!-- ERROR {e.code}: {e.reason} -->"
        except Exception as e:
            return f"<!-- ERROR: {e} -->"

    def post_binary(self, path, data):
        try:
            url = f"{SPPU_BASE}{urllib.parse.quote(path, safe='/')}"
            body = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            req.add_header("Referer", f"{SPPU_BASE}/Result/Dashboard/Default")
            req.add_header("Cookie", self._cookie_header())
            resp = urllib.request.urlopen(req, context=ssl_ctx, timeout=30)
            self._update_cookies(resp)
            ct = resp.headers.get("Content-Type", "application/pdf")
            return resp.read(), ct
        except urllib.error.HTTPError as e:
            return e.read(), "text/html"
        except Exception as e:
            return str(e).encode(), "text/plain"


sppu = SPPUSession()
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error(self, msg, status=500):
        self._send_json({"error": msg}, status)

    def _parse_path(self):
        parsed = urllib.parse.urlparse(self.path)
        return parsed.path, dict(urllib.parse.parse_qsl(parsed.query))

    def do_GET(self):
        path, params = self._parse_path()
        try:
            if path == "/api/sessions":
                data = sppu.get_text("/Result/Dashboard/GetSession")
                try:
                    parsed = json.loads(data)
                    self._send_json(parsed if isinstance(parsed, list) else [])
                except:
                    self._send_json([])

            elif path == "/api/courses":
                period = params.get("period", "")
                if period:
                    html = sppu.get_text("/Result/Dashboard/session", {"Exam_Period": period})
                else:
                    html = sppu.get_text("/Result/Dashboard/Default")
                self._send_json({"html": html or ""})

            elif path == "/api/captcha":
                result = sppu.post_json("/Result/Dashboard/RFCTLN")
                self._send_json(result)

            elif path == "/api/validate-captcha":
                ctxt = params.get("ctxt", "")
                hct = params.get("hct", "")
                result = sppu.post_json("/Result/Dashboard/VALCHCT", {"ctxt": ctxt, "hct": hct})
                self._send_json(result)

            elif path in ("/", "/index.html"):
                self.path = "/index.html"
                super().do_GET()

            elif path.startswith("/api/"):
                self._send_error(f"Unknown API: {path}")

            else:
                self.path = path
                super().do_GET()
        except Exception as e:
            self._send_error(f"Server error: {e}")
            traceback.print_exc()

    def do_POST(self):
        path, params = self._parse_path()
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else ""
            post_data = dict(urllib.parse.parse_qsl(body))

            if path == "/api/result":
                pdf_bytes, ct = sppu.post_binary("/SPPU ONLINE RESULT DISPLAY", post_data)
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Disposition", "inline; filename=result.pdf")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(pdf_bytes)

            elif path == "/api/captcha":
                result = sppu.post_json("/Result/Dashboard/RFCTLN")
                self._send_json(result)

            elif path == "/api/validate-captcha":
                ctxt = post_data.get("ctxt", "")
                hct = post_data.get("hct", "")
                result = sppu.post_json("/Result/Dashboard/VALCHCT", {"ctxt": ctxt, "hct": hct})
                self._send_json(result)

            else:
                self._send_error(f"Unknown POST: {path}")
        except Exception as e:
            self._send_error(f"Server error: {e}")
            traceback.print_exc()

    def log_message(self, format, *args):
        parts = " ".join(str(a) for a in args)
        print(f"[{self.log_date_time_string()}] {parts}")


if __name__ == "__main__":
    os.chdir(STATIC_DIR)
    httpd = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    httpd.timeout = 2
    print(f"\n  SPPU Result Server v2")
    print(f"  http://localhost:{PORT}/")
    print(f"  http://<your-ip>:{PORT}/\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"\nFatal: {e}")
