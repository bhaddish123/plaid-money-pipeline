"""One-time bank link. Opens a local page running Plaid Link; you log in to Wells Fargo
on Plaid's own screen. The resulting access token is saved to .plaid_token.json (0600).

Usage:
  python link.py            first-time link
  python link.py --update   re-authenticate if sync.py says ITEM_LOGIN_REQUIRED
"""
import json
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from plaid_common import TOKEN_FILE, PlaidError, load_env, load_token, plaid, write_private

HOST, PORT = "127.0.0.1", 8765
env = load_env()
update_mode = "--update" in sys.argv
nonce = secrets.token_urlsafe(24)  # one-time value; POSTs without it are rejected

body = {
    "user": {"client_user_id": "ket-local"},
    "client_name": "Ket Money Sync",
    "country_codes": ["US"],
    "language": "en",
}
if update_mode:
    body["access_token"] = load_token()["access_token"]
else:
    body["products"] = ["transactions"]
    body["transactions"] = {"days_requested": 730}

try:
    link_token = plaid(env, "/link/token/create", body)["link_token"]
except PlaidError as e:
    sys.exit(f"Could not create link token: {e}")

PAGE = f"""<!doctype html><meta charset=utf-8><title>Link bank</title>
<body style="font-family:system-ui;max-width:520px;margin:60px auto;padding:0 16px">
<h2>Connect your bank</h2><p id=s>Opening Plaid…</p>
<button id=b>Open Plaid Link</button>
<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
<script>
const s=document.getElementById('s');
const h=Plaid.create({{token:{json.dumps(link_token)},
 onSuccess:async(pt)=>{{s.textContent='Saving…';
  const r=await fetch('/exchange',{{method:'POST',headers:{{'Content-Type':'application/json'}},
   body:JSON.stringify({{public_token:pt,nonce:{json.dumps(nonce)}}})}});
  s.textContent=r.ok?'Done. You can close this tab.':'Failed: '+await r.text();}},
 onExit:(err)=>{{if(err)s.textContent='Exited: '+(err.error_message||err.error_code);}}}});
document.getElementById('b').onclick=()=>h.open(); h.open();
</script></body>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, text, ctype="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(text.encode())

    def do_GET(self):
        if self.path == "/":
            self._send(200, PAGE, "text/html")
        else:
            self._send(404, "not found")

    def do_POST(self):
        if self.path != "/exchange":
            return self._send(404, "not found")
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except Exception:
            return self._send(400, "bad request")
        if not secrets.compare_digest(str(data.get("nonce", "")), nonce):
            return self._send(403, "forbidden")
        if update_mode:
            self._send(200, "ok")
            print("Re-authenticated. Run: python sync.py")
        else:
            try:
                res = plaid(env, "/item/public_token/exchange", {"public_token": data["public_token"]})
            except (PlaidError, KeyError) as e:
                return self._send(500, str(e))
            write_private(TOKEN_FILE, {"access_token": res["access_token"], "item_id": res["item_id"]})
            self._send(200, "ok")
            print(f"Linked. Token saved to {TOKEN_FILE.name}. Now run: python sync.py")
        threading.Thread(target=server.shutdown, daemon=True).start()


server = HTTPServer((HOST, PORT), Handler)
url = f"http://{HOST}:{PORT}/"
print(f"Open {url} if your browser doesn't open automatically. Ctrl+C to cancel.")
webbrowser.open(url)
server.serve_forever()
