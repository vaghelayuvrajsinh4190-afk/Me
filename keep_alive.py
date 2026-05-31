from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"I'm alive!")

    def log_message(self, format, *args):
        # Silence default request logging to keep the bot console output neat
        return

def run_server():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), KeepAliveHandler)
    server.serve_forever()

def keep_alive():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
