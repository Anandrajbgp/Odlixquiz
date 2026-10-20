"""Railway ke liye chhota health-check HTTP server (sirf stdlib).

Railway Web Service me $PORT par kuch na kuch listen karna zaroori hai,
nahi to deploy "Offline" dikhta hai. Telegram bot polling background me
chalta rahega, ye server sirf Railway ko alive dikhane ke liye hai.
"""
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            body = b"OK - OdlixQuiz bot running"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # Railway logs me kachra na ho


def start_health_server():
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"Health server listening on 0.0.0.0:{port}")
    return server
