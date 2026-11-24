"""PROTOTYPE — throwaway. Build the 7 feature pages and serve each on its own localhost port.

Run:  python prototypes/sge_pattern_prototypes/serve.py      (Ctrl+C to stop)
Ports: 4181 callouts · 4182 CT setups · 4183 anchors · 4184 T tendencies · 4185 opening duels · 4186 all-games · 4187 vetoes
"""
import functools
import http.server
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    build.main()
    servers = []
    for key, port, title, _ in build.FEATURES:
        handler = functools.partial(Quiet, directory=os.path.join(build.OUT, key))
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        print(f"  {title:34} http://127.0.0.1:{port}/", flush=True)
    print("serving — Ctrl+C to stop", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
