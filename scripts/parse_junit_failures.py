#!/usr/bin/env python3
import sys
import os
import re
import xml.etree.ElementTree as ET

root_dir = sys.argv[1] if len(sys.argv) > 1 else "."

junit_paths = []
for dirpath, _dirnames, filenames in os.walk(root_dir):
    for fn in filenames:
        if fn.lower().endswith(".xml") and ("junit" in fn.lower() or "e2e" in fn.lower()):
            junit_paths.append(os.path.join(dirpath, fn))


def print_failure(case, kind, msg, text):
    classname = case.get("classname", "")
    name = case.get("name", "")
    print(f"[{kind}] {classname}::{name}")
    if msg:
        print(f"  message: {msg.strip()}")
    if text:
        lines = [ln.rstrip() for ln in text.strip().splitlines()]
        for ln in lines[:20]:
            print(f"  {ln}")
    print()


any_found = False
for p in junit_paths:
    try:
        tree = ET.parse(p)
        root = tree.getroot()
    except Exception:
        # Not a junit xml
        continue
    # pytest's JUnit uses <testsuite><testcase> ...
    for case in root.iter("testcase"):
        for child in case:
            tag = child.tag.lower()
            if tag in ("failure", "error"):
                any_found = True
                print_failure(case, tag.upper(), child.get("message", ""), child.text or "")

if not any_found:
    # Fallback: scan job log for FAILED lines
    log_path = os.path.join(root_dir, "e2e-job.log")
    if os.path.exists(log_path):
        print("# No JUnit failures parsed. Showing FAILED lines from job log:\n")
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if re.search(r"^FAILED\s", line) or "E   " in line:
                    print(line.rstrip())
    else:
        print("# No JUnit failures and no e2e-job.log present.")
