#!/usr/bin/env python3
"""
Serve the zrm chain and capture the log it POSTs back.

    python serve_zrm.py            # then open the printed URL on the PS4

`python -m http.server` answers POST with 501, so every log line the chain
sends is lost and the run looks silent. chain_lapse.js reports progress with

    POST t   (application/x-www-form-urlencoded)
    PS4-S4Q&tag=<tag>&detail=<detail>

This accepts those, prints them live, and writes them to zrm_log.txt.

Two things worth knowing before you run it:

  * Add ?verbose=1 to the URL. Without it the chain runs its log lines
    through terse(), which truncates at the first sentence break and caps
    them at 140 characters. With it you get the full text.

  * The page declares manifest="cache.appcache", so the console will keep
    serving the cached copy until the manifest itself changes. Edit any
    chain file without touching the manifest and the PS4 runs the old one.
    Pass --bump to rewrite the build comment and force a re-download.
"""

import http.server
import socketserver
import socket
import sys
import os
import re
import time
import datetime
import urllib.parse

PORT = 1992
ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(ROOT, "zrm_log.txt")


class C:
    if sys.platform == "win32":
        os.system("")
    R, B, D = "\033[0m", "\033[1m", "\033[2m"
    RED, GRN, YEL, BLU, CYN, MAG = ("\033[91m", "\033[92m", "\033[93m",
                                    "\033[94m", "\033[96m", "\033[95m")


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# Tags the chain uses carry their own severity; colour by what they say
# rather than guessing from position in the run.
def colour_for(tag, detail):
    t = (str(tag) + " " + str(detail)).lower()
    if re.search(r"\bfail|error|abort|refus|denied|bad\b|not found|missing", t):
        return C.RED
    if re.search(r"\bok\b|success|done|achieved|jailbroken|escalat|root|patched", t):
        return C.GRN
    if re.search(r"\bwarn|retry|attempt|slow|skip", t):
        return C.YEL
    return C.CYN


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        # Static hits are noise once the cache is warm; keep them dim and
        # out of the way so the chain's own log stands out.
        msg = fmt % args
        if "POST" in msg:
            return
        sys.stdout.write("%s%s  %s%s\n" % (C.D, now(), msg, C.R))

    def guess_type(self, path):
        if path.endswith(".appcache"):
            return "text/cache-manifest"
        return super().guess_type(path)

    def end_headers(self):
        # The manifest must never be stale-cached by an intermediary, or the
        # console will not notice a rebuilt chain.
        if self.path.endswith(".appcache"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_POST(self):
        if self.path.split("?", 1)[0].lstrip("/") != "t":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            n = 0
        raw = self.rfile.read(n).decode("utf-8", "replace") if n > 0 else ""

        q = urllib.parse.parse_qs(raw, keep_blank_values=True)
        tag = (q.get("tag") or [""])[0]
        detail = (q.get("detail") or [""])[0]

        col = colour_for(tag, detail)
        line = "%s  %s%-28s%s %s" % (now(), col + C.B, tag[:28], C.R, detail)
        print(line)

        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write("%s\t%s\t%s\n" % (now(), tag, detail))

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "2")
        self.end_headers()
        try:
            self.wfile.write(b"ok")
        except Exception:
            pass


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def bump_manifest():
    """Rewrite the build comment so the console re-downloads everything."""
    p = os.path.join(ROOT, "cache.appcache")
    if not os.path.isfile(p):
        print(C.RED + "  no cache.appcache here" + C.R)
        return
    txt = open(p, encoding="utf-8").read()
    stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    if re.search(r"^# build .*$", txt, re.M):
        txt = re.sub(r"^# build .*$", "# build local-" + stamp, txt, count=1, flags=re.M)
    else:
        txt = txt.replace("CACHE MANIFEST", "CACHE MANIFEST\n# build local-" + stamp, 1)
    open(p, "w", encoding="utf-8").write(txt)
    print(C.GRN + "  manifest bumped -> local-%s" % stamp + C.R)


def main():
    if "--bump" in sys.argv:
        bump_manifest()

    ip = lan_ip()
    print()
    print(C.CYN + C.B + "=" * 74 + C.R)
    print(C.CYN + C.B + "  zrm chain server" + C.R)
    print(C.CYN + "=" * 74 + C.R)
    print()
    print("  Open on the PS4 browser:")
    print("      " + C.GRN + C.B + "http://%s:%d/?verbose=1" % (ip, PORT) + C.R)
    print()
    print("  " + C.D + "?verbose=1 stops the chain truncating its log lines" + C.R)
    print("  " + C.D + "root: " + ROOT + C.R)
    print("  " + C.D + "log:  " + LOG + C.R)
    print()
    print("  " + C.D + "Edited a chain file? Run with --bump, or the console"
          + " keeps serving" + C.R)
    print("  " + C.D + "the copy it already cached." + C.R)
    print()
    print(C.D + "  Ctrl+C to stop" + C.R)
    print(C.CYN + "=" * 74 + C.R)
    print()

    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write("\n=== run %s ===\n" % datetime.datetime.now().isoformat(timespec="seconds"))

    try:
        with Server(("0.0.0.0", PORT), Handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print()
        print(C.YEL + "  Stopped. Log saved to %s" % LOG + C.R)
        print()
    except OSError as e:
        print(C.RED + "  Could not listen on %d: %s" % (PORT, e) + C.R)
        print(C.D + "  Port is busy - stop the other http.server first." + C.R)
        sys.exit(1)


if __name__ == "__main__":
    main()
