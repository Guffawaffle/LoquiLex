#!/usr/bin/env python3
import json, sys, re, os

in_f = "codeql-out/codeql-py.sarif"
out_f = "codeql-out/codeql-py-loquilex.sarif"
tri_f = "codeql-out/codeql-py-path-injection-triage.txt"
if not os.path.exists(in_f):
    print("SARIF not found:", in_f)
    sys.exit(2)
with open(in_f, "r") as f:
    sarif = json.load(f)
new_runs = []
for run in sarif.get("runs", []):
    results = run.get("results", [])
    kept = []
    for r in results:
        locs = r.get("locations", [])
        found = False
        for loc in locs:
            ar = loc.get("physicalLocation", {}).get("artifactLocation", {})
            uri = ar.get("uri", "")
            if "loquilex/" in uri.replace("file:///", ""):
                found = True
                break
        if found:
            kept.append(r)
    if kept:
        new_run = dict(run)
        new_run["results"] = kept
        new_runs.append(new_run)
new_sarif = {
    "version": sarif.get("version", ""),
    "$schema": sarif.get("$schema", ""),
    "runs": new_runs,
}
with open(out_f, "w") as f:
    json.dump(new_sarif, f, indent=2)
print("Wrote filtered SARIF:", out_f)
pat = re.compile(r"path.*inject", re.I)
triage = []
for run in new_runs:
    for r in run.get("results", []):
        rid = r.get("ruleId", "")
        if pat.search(rid) or pat.search(r.get("message", {}).get("text", "")):
            locs = r.get("locations", [])
            if locs:
                pl = locs[0].get("physicalLocation", {})
                ar = pl.get("artifactLocation", {})
                uri = ar.get("uri", "")
                region = pl.get("region", {})
                startLine = region.get("startLine")
            else:
                uri = ""
                startLine = None
            triage.append(
                {
                    "ruleId": rid,
                    "message": r.get("message", {}).get("text", ""),
                    "file": uri,
                    "line": startLine,
                }
            )
with open(tri_f, "w") as f:
    if not triage:
        f.write("No path-injection-like findings in loquilex/\n")
    else:
        for t in triage:
            f.write(f"{t['ruleId']} | {t['file']}:{t.get('line')}\n  {t['message']}\n\n")
print("Wrote triage file:", tri_f)
print("Path-injection-like findings count:", len(triage))
