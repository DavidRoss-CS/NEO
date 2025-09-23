import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/decide":
            self.send_response(404); self.end_headers(); return
        ln = int(self.headers.get("content-length","0"))
        payload = json.loads(self.rfile.read(ln) or "{}")
        strength = float(payload.get("strength", 0))
        decision = {
            "instrument": payload.get("instrument","?"),
            "side": "buy" if strength >= 0.55 else "skip",
            "size": 1 if strength >= 0.55 else 0,
            "confidence": round(strength, 2),
            "rationale": "demo",
            "ttl_ms": 60000 if strength >= 0.55 else 30000
        }
        out = json.dumps(decision).encode()
        self.send_response(200)
        self.send_header("content-type","application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

def main():
    port = int(sys.argv[1]) if len(sys.argv)>1 else 8082
    s = HTTPServer(("0.0.0.0", port), H)
    print(f"agent listening on {port}", flush=True)
    s.serve_forever()

if __name__ == "__main__":
    main()
