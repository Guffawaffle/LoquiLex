#!/usr/bin/env python3
"""Simple CLI to call POST /admin/cache/clear on local server.

Usage:
  LX_ADMIN_TOKEN=secret python scripts/clear_cache.py
  or
  python scripts/clear_cache.py --token secret
"""
import argparse
import os

import httpx


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=os.getenv("LX_API_URL", "http://127.0.0.1:8000"))
    p.add_argument("--token", default=os.getenv("LX_ADMIN_TOKEN"))
    args = p.parse_args(argv)

    if not args.token:
        print("No admin token provided. Set LX_ADMIN_TOKEN or pass --token.")
        return 2

    url = args.url.rstrip("/") + "/admin/cache/clear"
    headers = {"Authorization": f"Bearer {args.token}"}
    try:
        r = httpx.post(url, headers=headers, timeout=10)
        print(r.status_code, r.text)
        return 0 if r.status_code == 200 else 1
    except Exception as e:
        print("Request failed:", e)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
