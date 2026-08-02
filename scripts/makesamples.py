#!/usr/bin/env python3
"""Receive test cases from the Competitive Companion browser extension.

Listens on port 12345, waits for one task (or a whole batch, if you used
"parse all"), writes each one as ``<name>.cpp:tests`` and exits.

Usage:
    makesamples.py [NAME ...] [--ext cpp] [--port 12345] [--timeout 120]

With no NAME, files are named a.cpp:tests, b.cpp:tests, ... in batch order.

Uses only the standard library, so there is nothing to install.
"""

import argparse
import json
import os
import string
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

GREEN = "\033[0;32m"
RED = "\033[0;31m"
ORANGE = "\033[0;33m"
NO_COLOR = "\033[0m"


def convert(task):
    """Turn a Competitive Companion task into the format eval_samples.py reads."""
    return [
        {
            "test": t.get("input", ""),
            "correct_answers": [t["output"]] if t.get("output") is not None else [],
        }
        for t in task.get("tests", [])
    ]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length else b""

        # Answer before doing any work so the extension never sees a timeout.
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

        try:
            task = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            print(f"{RED}Ignoring malformed payload:{NO_COLOR} {e}")
            return

        self.server.on_task(task)

    def log_message(self, *_args):
        pass  # Silence the default per-request logging.


class Receiver(HTTPServer):
    def __init__(self, addr, names, ext):
        super().__init__(addr, Handler)
        self.names = names
        self.ext = ext
        self.expected = None   # learned from the first task's batch info
        self.received = 0
        self.done = False

    def name_for(self, index):
        if index < len(self.names):
            return self.names[index]
        if index < len(string.ascii_lowercase):
            return string.ascii_lowercase[index]
        return f"prob{index + 1}"

    def on_task(self, task):
        if self.expected is None:
            try:
                self.expected = int(task.get("batch", {}).get("size", 1) or 1)
            except (TypeError, ValueError):
                self.expected = 1
            if self.expected > 1:
                print(f"Batch of {self.expected} problems incoming...")

        name = self.name_for(self.received)
        path = f"{name}.{self.ext}:tests"
        tests = convert(task)

        if os.path.exists(path):
            print(f"{ORANGE}Overwriting existing {path}{NO_COLOR}")

        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(tests, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)

        print(f"{GREEN}Saved{NO_COLOR} {path}  ({len(tests)} tests)  "
              f"{task.get('name', '?')}")

        self.received += 1
        if self.received >= self.expected:
            self.done = True


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("names", nargs="*",
                   help="output name(s) without extension (default: a, b, c, ...)")
    p.add_argument("--ext", default="cpp", help="source extension (default cpp)")
    p.add_argument("--port", type=int, default=12345, help="listen port")
    p.add_argument("--timeout", type=float, default=120,
                   help="give up after this many seconds (default 120)")
    args = p.parse_args()

    try:
        server = Receiver(("127.0.0.1", args.port), args.names, args.ext)
    except OSError as e:
        print(f"{RED}ERROR:{NO_COLOR} cannot listen on port {args.port}: {e}")
        print("Another makesamples.py may still be running.")
        sys.exit(2)

    server.timeout = args.timeout
    print(f"Waiting for Competitive Companion on port {args.port} (Ctrl-C to cancel)...")

    try:
        while not server.done:
            before = server.received
            server.handle_request()      # also returns when server.timeout elapses
            if server.received == before:
                print(f"{RED}Timed out{NO_COLOR} after {args.timeout:g}s. "
                      "Did you click the Competitive Companion button?")
                sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
    finally:
        server.server_close()

    print("Done.")


if __name__ == "__main__":
    main()
