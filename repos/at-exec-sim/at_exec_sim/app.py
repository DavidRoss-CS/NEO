from http.server import BaseHTTPRequestHandler, HTTPServer
import json, sys

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/simulate":
            self.send_response(404); self.end_headers(); return
        ln = int(self.headers.get("content-length","0"))
        d = json.loads(self.rfile.read(ln) or "{}")
        if d.get("side") == "buy" and d.get("size",0) > 0:
            report = {"instrument": d.get("instrument","?"), "side":"buy", "qty": d.get("size",1), "fill_price": "28.412", "status":"filled", "pnl":"0.00"}
        else:
            report = {"instrument": d.get("instrument","?"), "side":"skip", "qty": 0, "status":"rejected", "reason":"RISK_CONF_LOW"}
        out = json.dumps(report).encode()
        self.send_response(200); self.send_header("content-type","application/json"); self.send_header("content-length", str(len(out))); self.end_headers()
        self.wfile.write(out)

def main():
    port = int(sys.argv[1]) if len(sys.argv)>1 else 8083
    s = HTTPServer(("0.0.0.0", port), H)
    print(f"exec-sim listening on {port}", flush=True)
    s.serve_forever()

if __name__ == "__main__":
    main()
