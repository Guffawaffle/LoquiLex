#!/usr/bin/env python3
"""
find-crashing-test.py
Run pytest tests one-by-one in isolated subprocesses to identify which test crashes Python/VS Code.
Writes per-test logs under ./crash-logs and stops at the first crash (unless --continue-on-crash).

Usage:
  python find-crashing-test.py [paths_or_nodeids ...]
Examples:
  python find-crashing-test.py                  # all tests discovered by pytest
  python find-crashing-test.py tests/test_api.py::test_ws_clean_shutdown
  python find-crashing-test.py tests -k resource and not slow

Notes:
- Forces offline-friendly env and single-threaded math libs.
- Detects "hard" crashes by non-zero return codes commonly used for segfault/abort and by scanning stderr.
"""
import argparse, os, sys, subprocess, shlex, time, pathlib, platform, re

def env_offline(base_env: dict) -> dict:
    env = dict(base_env)
    # Offline-first knobs
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    env.setdefault("LX_OFFLINE", "1")
    env.setdefault("PYTHONFAULTHANDLER", "1")
    env.setdefault("PYTHONASYNCIODEBUG", "1")
    # Tame native threads to reduce instability
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    # Sometimes uvloop/native extensions can be flaky on certain setups
    env.setdefault("UVLOOP_NO_EXTENSIONS", "1")
    return env

def collect_tests(paths: list[str], extra_args: list[str]) -> list[str]:
    cmd = ["pytest", "--collect-only", "-q", *paths, *extra_args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("Pytest collection failed.\nSTDOUT:\n", proc.stdout, "\nSTDERR:\n", proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    nodeids = [line.strip() for line in proc.stdout.splitlines() if line.strip() and not line.startswith("<Skipped") and "::" in line or line.endswith(".py")]
    # Pytest prints files and nodeids; keep nodeids primarily
    return nodeids

def is_hard_crash(rc: int, stderr: str) -> bool:
    # Common "hard" crashes: SIGSEGV=139, SIGABRT=134, Win STATUS_ACCESS_VIOLATION often 3221225477
    if rc in (134, 139, 3221225477, -11, -6):
        return True
    crash_markers = ("Segmentation fault", "Fatal Python error", "aborted", "stack overflow", "terminated by signal")
    return any(m.lower() in (stderr or "").lower() for m in crash_markers)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="Test paths or nodeids. If empty, run collection on the repo root.")
    ap.add_argument("-k", dest="kexpr", default=None, help="Pytest -k expression to filter tests.")
    ap.add_argument("--continue-on-crash", action="store_true", help="Do not stop at first crash; scan all tests.")
    ap.add_argument("--pytest-args", default="", help="Additional args to pass to pytest (quoted string).")
    ap.add_argument("--logs", default="crash-logs", help="Directory to write per-test logs.")
    args = ap.parse_args()

    logs_dir = pathlib.Path(args.logs).resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    extra = []
    if args.kexpr:
        extra += ["-k", args.kexpr]
    if args.pytest_args:
        extra += shlex.split(args.pytest_args)

    paths = args.paths or ["tests"]
    nodeids = collect_tests(paths, extra)

    if not nodeids:
        print("No tests collected.")
        return 0

    env = env_offline(os.environ)

    print(f"Collected {len(nodeids)} test(s). Running one-by-one...")
    for i, nodeid in enumerate(nodeids, 1):
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", nodeid)[:200]
        log_file = logs_dir / f"{i:04d}-{safe_name}.log"
        cmd = ["pytest", "-q", nodeid, *extra, "-x", "-s"]
        print(f"[{i}/{len(nodeids)}] {nodeid}")
        start = time.time()
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        elapsed = time.time() - start
        log_file.write_text(
            f"$ {' '.join(shlex.quote(c) for c in cmd)}\n\n"
            f"Return code: {proc.returncode}\n"
            f"Elapsed: {elapsed:.2f}s\n\n"
            f"=== STDOUT ===\n{proc.stdout}\n\n=== STDERR ===\n{proc.stderr}\n"
        )
        if proc.returncode != 0 and is_hard_crash(proc.returncode, proc.stderr):
            print("\n>>> HARD CRASH DETECTED <<<")
            print(f"Test: {nodeid}")
            print(f"Logs: {log_file}")
            if not args.continue_on_crash:
                print("Stopping at first crash. Re-run with --continue-on-crash to scan all.")
                return 1

    print("\nCompleted scan. Check logs under:", logs_dir)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
