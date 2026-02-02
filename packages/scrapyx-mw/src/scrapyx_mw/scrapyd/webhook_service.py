#!/usr/bin/env python3
"""
2captcha Webhook Receiver for Scrapyd hosts.
- POST /webhook with form data: id=<captcha_id>&code=<solution>
- GET  /health for status
Stores solutions in /var/lib/scrapyd/webhook_solutions.db (compatible with your existing project).
"""

import json, logging, os, sqlite3, threading, time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("webhook_service")

DB_PATH = "/var/lib/scrapyd/webhook_solutions.db"


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        p = urlparse(self.path)
        if p.path != "/webhook":
            self.send_error(404, "Not Found")
            return
        cl = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(cl).decode("utf-8")
        params = parse_qs(body)
        captcha_id = params.get("id", [None])[0]
        solution = params.get("code", [None])[0]

        if captcha_id and solution:
            self._store(captcha_id, solution)
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_error(400, "Bad Request")

    def do_GET(self):
        if self.path == "/health":
            resp = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "solutions_count": self._count(),
            }
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        elif self.path == "/2captcha.txt":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"verification-token-placeholder")
        else:
            self.send_error(404, "Not Found")

    def log_message(self, fmt, *args):
        logger.info("%s - " + fmt, self.address_string(), *args)

    def _store(self, captcha_id: str, solution: str):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
            CREATE TABLE IF NOT EXISTS captcha_solutions (
                captcha_id TEXT PRIMARY KEY,
                solution   TEXT NOT NULL,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used BOOLEAN DEFAULT FALSE
            )
            """)
            c.execute(
                """
            INSERT OR REPLACE INTO captcha_solutions (captcha_id, solution, received_at, used)
            VALUES (?, ?, ?, ?)
            """,
                (captcha_id, solution, datetime.now(), False),
            )
            conn.commit()
            conn.close()
            logger.info("Stored solution for captcha %s", captcha_id)
        except Exception as e:
            logger.error("DB store error: %s", e)

    def _count(self) -> int:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM captcha_solutions")
            n = c.fetchone()[0]
            conn.close()
            return int(n)
        except Exception:
            return 0


class WebhookService:
    def __init__(self, host="127.0.0.1", port=6801):
        self.host = host
        self.port = port
        self.server = None
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        t = threading.Thread(target=self._cleanup, daemon=True)
        t.start()

    def start(self):
        try:
            self.server = HTTPServer((self.host, self.port), WebhookHandler)
            logger.info(
                "Webhook service on %s:%s (DB: %s)", self.host, self.port, DB_PATH
            )
            self.server.serve_forever()
        except Exception as e:
            logger.error("Start failed: %s", e)
            raise

    def stop(self):
        if self.server:
            self.server.shutdown()
            logger.info("Webhook service stopped")

    def _cleanup(self):
        while True:
            try:
                time.sleep(3600)
                cutoff = datetime.now() - timedelta(hours=1)
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute(
                    "DELETE FROM captcha_solutions WHERE received_at < ?", (cutoff,)
                )
                deleted = c.rowcount
                conn.commit()
                conn.close()
                if deleted > 0:
                    logger.info("Cleaned up %s old solutions", deleted)
            except Exception as e:
                logger.error("Cleanup error: %s", e)


def get_solution(captcha_id: str) -> str | None:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT solution FROM captcha_solutions WHERE captcha_id=? AND used=FALSE",
            (captcha_id,),
        )
        row = c.fetchone()
        if row:
            c.execute(
                "UPDATE captcha_solutions SET used=TRUE WHERE captcha_id=?",
                (captcha_id,),
            )
            conn.commit()
            conn.close()
            return row[0]
        conn.close()
        return None
    except Exception as e:
        logger.error("Get solution error: %s", e)
        return None


if __name__ == "__main__":
    svc = WebhookService()
    try:
        svc.start()
    except KeyboardInterrupt:
        svc.stop()
