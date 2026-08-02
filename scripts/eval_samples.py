#!/usr/bin/env python3
"""Run a compiled competitive-programming solution against its sample tests.

Tests come from two places:

  * a Competitive Companion json file next to the source, named
    ``<target>.cpp:tests`` (any source extension works, e.g. ``a.py:tests``)
  * loose ``inN.txt`` / ``ansN.txt`` pairs in the working directory

Usage:
    eval_samples.py TARGET [DIR]

TARGET is the executable, with or without a source extension. DIR is optional
and only exists so the old two-argument call from wtrunner.py keeps working;
when given, it is used as the working directory.

Exits 0 when every test passes, 1 otherwise, so it can be chained in a build.
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time

GREEN = "\033[0;32m"
RED = "\033[0;31m"
ORANGE = "\033[0;33m"
BLUE = "\033[0;34m"
DIM = "\033[2m"
NO_COLOR = "\033[0m"

AC, WA, RE, TLE, NO_ANS = "AC", "WA", "RE", "TLE", "??"

VERDICT_COLOR = {AC: GREEN, WA: RED, RE: RED, TLE: ORANGE, NO_ANS: ORANGE}

# Source extensions we strip off TARGET, and try when looking for the json file.
SOURCE_EXTS = ("cpp", "cc", "cxx", "c", "py", "java", "rs", "go", "kt")

DEFAULT_TIMEOUT = float(os.environ.get("EVAL_TIMEOUT", "10"))


class Test:
    """A single test case. `answers` holds every output accepted as correct."""

    def __init__(self, label, data, answers):
        self.label = label
        self.data = data
        self.answers = answers
        self.last_out = None
        self.verdict = None


def die(msg):
    print(f"{RED}ERROR:{NO_COLOR} {msg}")
    sys.exit(2)


# --------------------------------------------------------------------------
# locating things
# --------------------------------------------------------------------------

def resolve_target(raw):
    """Return (executable_path, stem) for the user-supplied TARGET."""
    stem = raw
    for ext in SOURCE_EXTS:
        if stem.endswith("." + ext):
            stem = stem[: -(len(ext) + 1)]
            break

    exe = stem
    # A bare name is a path in the current directory, not a PATH lookup.
    if os.path.dirname(exe) == "":
        exe = os.path.join(".", exe)
    return exe, stem


def find_tests_file(stem):
    """Competitive Companion writes '<source>:tests'; find whichever exists."""
    for ext in SOURCE_EXTS:
        path = f"{stem}.{ext}:tests"
        if os.path.exists(path):
            return path
    # Nothing on disk yet: default to the C++ name so `new` can create it.
    return f"{stem}.cpp:tests"


def normalize(entry):
    """Accept both our format and raw Competitive Companion entries."""
    if "test" in entry:
        data = entry["test"]
    else:
        data = entry.get("input", "")

    if "correct_answers" in entry:
        answers = list(entry["correct_answers"])
    elif entry.get("output") is not None:
        answers = [entry["output"]]
    else:
        answers = []
    return data, answers


def load_json_tests(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read().strip()
    except OSError as e:
        die(f"could not read {path}: {e}")

    if not raw:
        # An empty file is a normal state right after `touch`; not an error.
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"{path} is not valid json: {e}")

    # Competitive Companion's own dump nests the list under "tests".
    if isinstance(parsed, dict):
        parsed = parsed.get("tests", [])

    tests = []
    for i, entry in enumerate(parsed):
        data, answers = normalize(entry)
        tests.append(Test(str(i), data, answers))
    return tests


def save_json_tests(path, tests):
    """Write atomically so an interrupted save cannot truncate the file."""
    payload = [{"test": t.data, "correct_answers": t.answers} for t in tests]
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except OSError as e:
        die(f"could not write {path}: {e}")


def load_file_tests():
    """Pick up every inN.txt in the cwd, with its ansN.txt if present."""
    tests = []
    for name in sorted(os.listdir("."), key=file_test_key):
        m = re.fullmatch(r"in(\d+)\.txt", name)
        if not m:
            continue
        num = m.group(1)
        try:
            with open(name, encoding="utf-8") as f:
                data = f.read()
        except OSError as e:
            print(f"{ORANGE}skipping {name}: {e}{NO_COLOR}")
            continue

        answers = []
        for cand in (f"ans{num}.txt", f"out{num}.txt", f"exp{num}.txt"):
            if os.path.exists(cand):
                with open(cand, encoding="utf-8") as f:
                    answers.append(f.read())
                break
        tests.append(Test(f"file {num}", data, answers))
    return tests


def file_test_key(name):
    m = re.fullmatch(r"in(\d+)\.txt", name)
    return (0, int(m.group(1))) if m else (1, 0)


# --------------------------------------------------------------------------
# running and judging
# --------------------------------------------------------------------------

def run_program(exe, stdin_data, timeout):
    """Return (stdout, stderr, verdict_or_None, elapsed_seconds, note)."""
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [exe],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        die(f"executable not found: {exe} (did build.sh run?)")
    except PermissionError:
        die(f"not executable: {exe}")
    except subprocess.TimeoutExpired as e:
        elapsed = time.monotonic() - start
        out = e.stdout or ""
        err = e.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        return out, err, TLE, elapsed, f"exceeded {timeout:g}s"

    elapsed = time.monotonic() - start

    if proc.returncode < 0:
        sig = -proc.returncode
        try:
            name = signal.Signals(sig).name
        except ValueError:
            name = f"signal {sig}"
        return proc.stdout, proc.stderr, RE, elapsed, f"killed by {name}"
    if proc.returncode != 0:
        return proc.stdout, proc.stderr, RE, elapsed, f"exit code {proc.returncode}"

    return proc.stdout, proc.stderr, None, elapsed, ""


def matches(got, expected, exact):
    """Whitespace-insensitive by default, which is what judges actually do."""
    if exact:
        return got.rstrip() == expected.rstrip()
    return got.split() == expected.split()


def first_difference(got, expected):
    """Describe where two token streams diverge, for a useful WA message."""
    g, e = got.split(), expected.split()
    for i, (a, b) in enumerate(zip(g, e)):
        if a != b:
            return f"token {i}: expected {b!r}, got {a!r}"
    if len(g) != len(e):
        return f"expected {len(e)} tokens, got {len(g)}"
    return "outputs differ only in whitespace"


def eval_test(test, exe, timeout, exact):
    print(f"{BLUE}Test {test.label}:{NO_COLOR}")
    print(test.data.rstrip("\n"))
    print("My answer:")

    out, err, verdict, elapsed, note = run_program(exe, test.data, timeout)

    print(out.rstrip("\n") if out.strip() else f"{DIM}(no output){NO_COLOR}")
    if err.strip():
        # Debug output from the template goes to stderr; show it, never judge it.
        print(f"{ORANGE}stderr:{NO_COLOR}")
        print(err.rstrip("\n"))

    test.last_out = out

    if verdict is None:
        if not test.answers:
            verdict = NO_ANS
            note = "no expected answer saved"
        elif any(matches(out, a, exact) for a in test.answers):
            verdict = AC
        else:
            verdict = WA
            note = first_difference(out, test.answers[0])

    if verdict in (WA, NO_ANS):
        print("\nSample answer:")
        if test.answers:
            print(test.answers[0].rstrip("\n"))
        else:
            print(f"{ORANGE}(none saved){NO_COLOR}")

    color = VERDICT_COLOR[verdict]
    timing = f"{DIM}{elapsed * 1000:.0f} ms{NO_COLOR}"
    suffix = f" {DIM}({note}){NO_COLOR}" if note else ""
    print(f"\n[VERDICT: {color}{verdict}{NO_COLOR}] {timing}{suffix}")
    print("--------------\n")

    test.verdict = verdict
    return verdict


def print_summary(json_tests, file_tests):
    if not any(t.verdict for t in json_tests + file_tests):
        return
    print("Summary:")
    for title, group in (("Tests from json file:", json_tests),
                         ("Tests from txt files:", file_tests)):
        group = [t for t in group if t.verdict is not None]
        if not group:
            continue
        print(f"  {title}")
        for t in group:
            color = VERDICT_COLOR[t.verdict]
            print(f"    Test {t.label}: {color}{t.verdict}{NO_COLOR}")
    print("")


def all_passed(tests):
    return all(t.verdict == AC for t in tests if t.verdict is not None)


# --------------------------------------------------------------------------
# interactive console
# --------------------------------------------------------------------------

HELP = """
    Commands:

    run [n]        Run every test, or just json test n.
    runf n         Run the test loaded from in<n>.txt.
    ac n           Accept the last output of json test n as correct (n=-1: all).
    wa n           Un-accept the last output of json test n.
    new            Read a test from stdin (Ctrl-D to finish) and save it.
    del n          Delete json test n.
    dpans n        Show the saved correct answers for json test n.
    list           List all tests with their latest verdict.
    numtests       Print the number of tests.
    help           This message.
    quit / q       Exit. Ctrl-D also works.
"""


class Console:
    def __init__(self, exe, tests_path, json_tests, file_tests, timeout, exact):
        self.exe = exe
        self.tests_path = tests_path
        self.json_tests = json_tests
        self.file_tests = file_tests
        self.timeout = timeout
        self.exact = exact

    # -- helpers ----------------------------------------------------------

    def run_one(self, test):
        try:
            eval_test(test, self.exe, self.timeout, self.exact)
        except KeyboardInterrupt:
            # Abort this test only; keep the console alive.
            print(f"\n{ORANGE}interrupted{NO_COLOR}\n")

    def run_all(self):
        for t in self.json_tests + self.file_tests:
            self.run_one(t)
        print_summary(self.json_tests, self.file_tests)

    def save(self):
        save_json_tests(self.tests_path, self.json_tests)

    def index(self, args, cmd):
        """Parse and bounds-check a json test index argument."""
        if not args:
            print(f"{ORANGE}{cmd} needs a test number{NO_COLOR}")
            return None
        try:
            n = int(args[0])
        except ValueError:
            print(f"{ORANGE}'{args[0]}' is not a number{NO_COLOR}")
            return None
        if not 0 <= n < len(self.json_tests):
            print(f"{ORANGE}no json test {n} (have {len(self.json_tests)}){NO_COLOR}")
            return None
        return n

    # -- commands ---------------------------------------------------------

    def cmd_run(self, args):
        if not args or args[0] == "-1":
            self.run_all()
            return
        n = self.index(args, "run")
        if n is not None:
            self.run_one(self.json_tests[n])

    def cmd_runf(self, args):
        if not args:
            print(f"{ORANGE}runf needs a test number{NO_COLOR}")
            return
        for t in self.file_tests:
            if t.label == f"file {args[0]}":
                self.run_one(t)
                return
        print(f"{ORANGE}no in{args[0]}.txt loaded{NO_COLOR}")

    def cmd_ac(self, args):
        if args and args[0] == "-1":
            targets = self.json_tests
        else:
            n = self.index(args, "ac")
            if n is None:
                return
            targets = [self.json_tests[n]]

        changed = False
        for t in targets:
            if t.last_out is None:
                print(f"{ORANGE}test {t.label} has not been run yet{NO_COLOR}")
                continue
            if t.last_out not in t.answers:
                t.answers.append(t.last_out)
                changed = True
        if changed:
            self.save()
        for t in targets:
            self.run_one(t)
        if len(targets) > 1:
            print_summary(self.json_tests, [])

    def cmd_wa(self, args):
        n = self.index(args, "wa")
        if n is None:
            return
        t = self.json_tests[n]
        if t.last_out is not None and t.last_out in t.answers:
            t.answers.remove(t.last_out)
            self.save()
        self.run_one(t)

    def cmd_new(self, args):
        print("Input the test case and press Ctrl-D to save it.")
        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass
        except KeyboardInterrupt:
            print(f"\n{ORANGE}cancelled{NO_COLOR}")
            return
        data = "".join(line + "\n" for line in lines)
        if not data.strip():
            print(f"{ORANGE}empty test, nothing added{NO_COLOR}")
            return
        self.json_tests.append(Test(str(len(self.json_tests)), data, []))
        self.save()
        print(f"Added test {len(self.json_tests) - 1}.")

    def cmd_del(self, args):
        n = self.index(args, "del")
        if n is None:
            return
        self.json_tests.pop(n)
        for i, t in enumerate(self.json_tests):
            t.label = str(i)
        self.save()
        print(f"Deleted test {n}.")

    def cmd_dpans(self, args):
        n = self.index(args, "dpans")
        if n is None:
            return
        t = self.json_tests[n]
        if not t.answers:
            print(f"{ORANGE}No correct answers saved for test {n}{NO_COLOR}")
            return
        print("Correct answers:")
        for i, a in enumerate(t.answers):
            print(f"Answer {i}:")
            print(a.rstrip("\n"))
            print("")

    def cmd_list(self, args):
        for t in self.json_tests + self.file_tests:
            v = t.verdict or "-"
            color = VERDICT_COLOR.get(t.verdict, DIM)
            first = t.data.strip().splitlines()[:1]
            preview = first[0][:40] if first else ""
            print(f"  {t.label:>8}  {color}{v:<2}{NO_COLOR}  {DIM}{preview}{NO_COLOR}")

    def cmd_numtests(self, args):
        print(f"json tests: {len(self.json_tests)}, file tests: {len(self.file_tests)}")

    def cmd_help(self, args):
        print(HELP)

    COMMANDS = {
        "run": cmd_run, "runf": cmd_runf, "ac": cmd_ac, "wa": cmd_wa,
        "new": cmd_new, "del": cmd_del, "dpans": cmd_dpans, "list": cmd_list,
        "numtests": cmd_numtests, "help": cmd_help, "?": cmd_help,
    }

    def loop(self):
        print('Test Case Evaluator Console (type "help" for commands, "quit" to exit)')
        while True:
            try:
                line = input(">>> ")
            except (EOFError, KeyboardInterrupt):
                print("")
                return
            parts = line.split()
            if not parts:
                continue
            cmd, args = parts[0].lower(), parts[1:]
            if cmd in ("quit", "q", "exit"):
                return
            handler = self.COMMANDS.get(cmd)
            if handler is None:
                print(f"{ORANGE}unknown command '{cmd}' (try 'help'){NO_COLOR}")
                continue
            try:
                handler(self, args)
            except KeyboardInterrupt:
                print(f"\n{ORANGE}interrupted{NO_COLOR}")


# --------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="Run a solution against its sample tests.")
    p.add_argument("target", help="executable / source name, with or without extension")
    p.add_argument("directory", nargs="?",
                   help="working directory (legacy wtrunner.py argument)")
    p.add_argument("-t", "--timeout", type=float, default=DEFAULT_TIMEOUT,
                   help=f"per-test time limit in seconds (default {DEFAULT_TIMEOUT:g})")
    p.add_argument("-e", "--exact", action="store_true",
                   help="require exact output match instead of token comparison")
    p.add_argument("-n", "--no-repl", action="store_true",
                   help="run the tests and exit, without the interactive console")
    args = p.parse_args()

    if args.directory:
        try:
            os.chdir(args.directory)
        except OSError as e:
            die(f"cannot enter {args.directory}: {e}")

    exe, stem = resolve_target(args.target)
    tests_path = find_tests_file(stem)

    print("")
    json_tests = load_json_tests(tests_path)
    file_tests = load_file_tests()

    if not json_tests and not file_tests:
        print(f"{ORANGE}No tests found.{NO_COLOR} Looked for "
              f"{os.path.basename(tests_path)} and in*.txt in {os.getcwd()}.")

    console = Console(exe, tests_path, json_tests, file_tests,
                      args.timeout, args.exact)
    console.run_all()

    if not args.no_repl and sys.stdin.isatty():
        console.loop()

    sys.exit(0 if all_passed(json_tests + file_tests) else 1)


if __name__ == "__main__":
    main()
