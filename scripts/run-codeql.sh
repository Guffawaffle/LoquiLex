#!/usr/bin/env bash
set -euo pipefail

# run-codeql.sh — Build CodeQL DBs, analyze JS/TS + Python, and print results.
# Requires: codeql. Optional: jq (pretty summaries), column (tabular formatting).

# ---- Config (overridable via env or flags) ----
# Prefer the repository toplevel if inside a git repo; else PWD.
_default_repo_root() {
  if command -v git >/dev/null 2>&1; then
    git rev-parse --show-toplevel 2>/dev/null || pwd
  else
    pwd
  fi
}

REPO_ROOT="${REPO_ROOT:-$(_default_repo_root)}"
OUT_DIR="${OUT_DIR:-codeql-out}"
DB_JS="${DB_JS:-ql-db-js}"
DB_PY="${DB_PY:-ql-db-py}"
PK_JS="codeql/javascript-queries"
JS_SUITE_QUALITY="codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls"
JS_SUITE_EXTENDED="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
PK_PY="codeql/python-queries"
PY_SUITE_QUALITY="codeql/python-queries:codeql-suites/python-security-and-quality.qls"
PY_SUITE_EXTENDED="codeql/python-queries:codeql-suites/python-security-extended.qls"
SUITE_SUFFIX=""      # "" or ":security-extended"
DOWNLOAD="--download"
CREATE_DBS=1
VERBOSE=0
THREADS=0             # 0 = CodeQL default
NO_SUMMARY=0          # 1 = skip jq-based summaries

usage() {
  cat <<'USAGE'
Usage: ./run-codeql.sh [OPTIONS]
  or: ./run-codeql.sh view [VIEW OPTIONS]
  or: ./run-codeql.sh report [REPORT OPTIONS]
  or: ./run-codeql.sh export [EXPORT OPTIONS]

Options:
  --extended        Use the broader :security-extended suite
  --no-create       Skip database (re)creation; reuse existing DBs
  --out DIR         Output directory (default: codeql-out)
  --repo-root DIR   Source root (default: git toplevel or CWD)
  --db-js PATH      Path for JS/TS CodeQL DB (default: ql-db-js)
  --db-py PATH      Path for Python CodeQL DB (default: ql-db-py)
  --threads N       Threads for analyze step (default: CodeQL default)
  --offline         Do not download packs (omit --download)
  --no-summary      Skip jq summaries; only print SARIF paths
  --min-level L     Minimum level to include: none|note|warning|error (default: none)
  --fail-on L       Exit non-zero if any finding >= level L
  -v, --verbose     Print extra logging
  -h, --help        Show this help

View options (when using subcommand "view" or flag --view):
  --sarif PATH      Summarize this SARIF file (repeatable)
  --lang js|py|all  Select default SARIF(s) in --out (default: all)
  --limit N         Sample findings row limit (default: 25)
  --open            Open SARIF file(s) in default viewer (if supported)

Report options (when using subcommand "report"):
  --out DIR         Output directory (default: codeql-out)
  --lang js|py|all  Which SARIFs to include (default: all)

Export options (when using subcommand "export"):
  --sarif PATH      Source SARIF (repeatable; default: from --out and --lang)
  --out-json PATH   Write triage JSON (default: codeql-out/findings.json)
  --min-level L     Minimum level to include: none|note|warning|error

Examples:
  ./run-codeql.sh
  ./run-codeql.sh --extended
  ./run-codeql.sh --no-create --out /tmp/ql
  ./run-codeql.sh view --lang js --out codeql-out
  ./run-codeql.sh --view --sarif codeql-out/codeql-py.sarif --limit 50
USAGE
}

log() { printf '%s\n' "$*" >&2; }
vlog() { (( VERBOSE )) && log "$@"; }

have() { command -v "$1" >/dev/null 2>&1; }

ACTION="analyze"
SARIF_PATHS=()
LANG_FILTER="all"  # js | py | all
SAMPLE_LIMIT=25
OPEN_VIEW=0
MIN_LEVEL="none"
FAIL_ON="none"
OUT_JSON=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    view|--view) ACTION="view"; shift ;;
    report) ACTION="report"; shift ;;
    export) ACTION="export"; shift ;;
    --extended) SUITE_SUFFIX=":security-extended"; shift ;;
    --no-create) CREATE_DBS=0; shift ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --repo-root) REPO_ROOT="$2"; shift 2 ;;
    --db-js) DB_JS="$2"; shift 2 ;;
    --db-py) DB_PY="$2"; shift 2 ;;
    --threads) THREADS="$2"; shift 2 ;;
    --offline) DOWNLOAD=""; shift ;;
    --no-summary) NO_SUMMARY=1; shift ;;
    --sarif) SARIF_PATHS+=("$2"); shift 2 ;;
    --lang)
      case "${2,,}" in
        js|py|all) LANG_FILTER="${2,,}" ;;
        *) log "Invalid --lang: $2 (expected js|py|all)"; exit 2 ;;
      esac
      shift 2 ;;
    --limit)
      [[ "$2" =~ ^[0-9]+$ ]] || { log "--limit expects integer"; exit 2; }
      SAMPLE_LIMIT="$2"; shift 2 ;;
    --open) OPEN_VIEW=1; shift ;;
    --min-level)
      case "${2,,}" in
        none|note|warning|error) MIN_LEVEL="${2,,}" ;;
        *) log "Invalid --min-level: $2 (expected none|note|warning|error)"; exit 2 ;;
      esac
      shift 2 ;;
    --fail-on)
      case "${2,,}" in
        none|note|warning|error) FAIL_ON="${2,,}" ;;
        *) log "Invalid --fail-on: $2 (expected none|note|warning|error)"; exit 2 ;;
      esac
      shift 2 ;;
    --out-json) OUT_JSON="$2"; shift 2 ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) log "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

# ---- Pre-flight: shared output dir ----
mkdir -p "$OUT_DIR"

# ---- Helper: summarize SARIF with jq (if available) ----
summarize_sarif() {
  local sarif="$1" limit="${2:-$SAMPLE_LIMIT}"
  if (( NO_SUMMARY )); then
    echo "Results: $sarif"
    return 0
  fi

  if ! have jq; then
    log "Note: jq not found — showing file path instead."
    echo "Results: $sarif"
    return 0
  fi

  # Use column if present; otherwise pass-through TSV for readability.
  fmt_columns() {
    local sep="$1"; shift || true
    if have column; then
      column -t -s "$sep"
    else
      cat
    fi
  }

  echo "══════════════════════════════════════════════════════════════════════"
  echo "Summary for: $sarif"
  echo "---------------------------------------------------------------------"
  # Counts by severity level
  jq -r --arg min "$MIN_LEVEL" '
    def norm(l): if l==null then "warning" else l end;
    def ge(a;b):
      {"none":0,"note":1,"warning":2,"error":3}[a] <= {"none":0,"note":1,"warning":2,"error":3}[b];
    [.runs[].results[]? | . as $r | norm($r.level) as $lvl | select( ge($min; $lvl) ) | $lvl]
    | group_by(.) | map({level: .[0], count: length}) | sort_by(.level)
    | (["Severity","Count"], ["--------","-----"]) , ( .[] | [ .level, (.count|tostring) ])
    | @tsv
  ' "$sarif" | fmt_columns $'\t'

  echo
  echo "Top rules (ruleId: count):"
  jq -r '
    [.runs[].results[]? | .ruleId] | group_by(.) |
    map({rule: .[0], count: length}) | sort_by(-.count) |
    .[0:20] | map("\(.rule): \(.count)") | .[]
  ' "$sarif"

  echo
  echo "Sample findings (ruleId | level | file:line | message):"
  jq -r --arg min "$MIN_LEVEL" '
    .runs[]
    | .tool.driver.rules as $rules
    | .results[]?
    | . as $r | ($r.level // "warning") as $lvl | {"none":0,"note":1,"warning":2,"error":3} as $ord
    | select($ord[$min] <= $ord[$lvl])
    | [
        .ruleId,
        $lvl,
        (
          (.locations[0].physicalLocation.artifactLocation.uri // "?")
          + ":"
          + ((.locations[0].physicalLocation.region.startLine // 0)|tostring)
        ),
        (.message.text // "")
      ] | @tsv
  ' "$sarif" | head -n "$limit" | fmt_columns $'\t'
  echo "══════════════════════════════════════════════════════════════════════"
}

# ---- View mode (summarize existing SARIF) ----
if [[ "$ACTION" == "view" ]]; then
  vlog "[view] Summarizing SARIF results..."
  if (( ${#SARIF_PATHS[@]} )); then
    for p in "${SARIF_PATHS[@]}"; do
      [[ -f "$p" ]] || { log "ERROR: SARIF not found: $p"; exit 1; }
      summarize_sarif "$p" "$SAMPLE_LIMIT"
    done
    echo "Done."
    exit 0
  fi

  # Fall back to defaults in OUT_DIR
  js_path="$OUT_DIR/codeql-js.sarif"
  py_path="$OUT_DIR/codeql-py.sarif"
  found_any=0
  if [[ "$LANG_FILTER" == "js" || "$LANG_FILTER" == "all" ]]; then
    if [[ -f "$js_path" ]]; then
      summarize_sarif "$js_path" "$SAMPLE_LIMIT"; found_any=1
    else
      vlog "No JS SARIF at $js_path"
    fi
  fi
  if [[ "$LANG_FILTER" == "py" || "$LANG_FILTER" == "all" ]]; then
    if [[ -f "$py_path" ]]; then
      summarize_sarif "$py_path" "$SAMPLE_LIMIT"; found_any=1
    else
      vlog "No Python SARIF at $py_path"
    fi
  fi
  if (( ! found_any )); then
    log "No SARIF files found in $OUT_DIR. Run analysis first."
    exit 1
  fi
  echo "Done."
  exit 0
fi

# ---- Report mode (generate simple HTML index) ----
if [[ "$ACTION" == "report" ]]; then
  mkdir -p "$OUT_DIR"
  js_path="$OUT_DIR/codeql-js.sarif"
  py_path="$OUT_DIR/codeql-py.sarif"
  html="$OUT_DIR/index.html"

  summarize_count() {
    local sarif="$1"
    if have jq; then
      jq -r --arg min "$MIN_LEVEL" '
        def norm(l): if l==null then "warning" else l end;
        def ge(a;b): {"none":0,"note":1,"warning":2,"error":3}[a] <= {"none":0,"note":1,"warning":2,"error":3}[b];
        [.runs[].results[]? | norm(.level) as $lvl | select( ge($min; $lvl) )] | length
      ' "$sarif" 2>/dev/null || echo 0
    else
      echo "jq not available"
    fi
  }

  {
    echo "<!doctype html>"
    echo "<html><head><meta charset=\"utf-8\"><title>CodeQL Report</title>"
    echo "<style>body{font-family:system-ui,Arial,sans-serif;margin:2rem} code{background:#f3f3f3;padding:.1rem .3rem;border-radius:4px}</style>"
    echo "</head><body>"
    echo "<h1>CodeQL Report</h1>"
    echo "<p>Output directory: <code>$OUT_DIR</code></p>"

    if [[ "$LANG_FILTER" == "js" || "$LANG_FILTER" == "all" ]]; then
      if [[ -f "$js_path" ]]; then
        cnt=$(summarize_count "$js_path")
        echo "<h2>JavaScript/TypeScript</h2>"
        echo "<p>Findings (>= $MIN_LEVEL): <strong>$cnt</strong></p>"
        echo "<p><a href=\"codeql-js.sarif\">Download SARIF</a></p>"
      else
        echo "<h2>JavaScript/TypeScript</h2><p><em>No SARIF found at $js_path</em></p>"
      fi
    fi

    if [[ "$LANG_FILTER" == "py" || "$LANG_FILTER" == "all" ]]; then
      if [[ -f "$py_path" ]]; then
        cnt=$(summarize_count "$py_path")
        echo "<h2>Python</h2>"
        echo "<p>Findings (>= $MIN_LEVEL): <strong>$cnt</strong></p>"
        echo "<p><a href=\"codeql-py.sarif\">Download SARIF</a></p>"
      else
        echo "<h2>Python</h2><p><em>No SARIF found at $py_path</em></p>"
      fi
    fi

    echo "</body></html>"
  } >"$html"

  echo "Report written to: $html"

  # Optional failure if threshold breached
  if have jq && [[ "$FAIL_ON" != "none" ]]; then
    js_cnt=0; py_cnt=0
    [[ -f "$js_path" ]] && js_cnt=$(summarize_count "$js_path")
    [[ -f "$py_path" ]] && py_cnt=$(summarize_count "$py_path")
    if (( (js_cnt + py_cnt) > 0 )); then
      log "Failing due to --fail-on=$FAIL_ON with $((js_cnt+py_cnt)) findings"
      exit 3
    fi
  fi

  exit 0
fi

# ---- Export mode (write simplified JSON for triage) ----
if [[ "$ACTION" == "export" ]]; then
  mkdir -p "$OUT_DIR"
  js_path="$OUT_DIR/codeql-js.sarif"
  py_path="$OUT_DIR/codeql-py.sarif"
  paths=()
  if (( ${#SARIF_PATHS[@]} )); then
    paths=("${SARIF_PATHS[@]}")
  else
    [[ "$LANG_FILTER" == "js" || "$LANG_FILTER" == "all" ]] && [[ -f "$js_path" ]] && paths+=("$js_path")
    [[ "$LANG_FILTER" == "py" || "$LANG_FILTER" == "all" ]] && [[ -f "$py_path" ]] && paths+=("$py_path")
  fi
  [[ ${#paths[@]} -gt 0 ]] || { log "No SARIF to export."; exit 1; }

  out_json="${OUT_JSON:-$OUT_DIR/findings.json}"
  if have jq; then
    jq -s --arg min "$MIN_LEVEL" '
      def norm(l): if l==null then "warning" else l end;
      def ge(a;b): {"none":0,"note":1,"warning":2,"error":3}[a] <= {"none":0,"note":1,"warning":2,"error":3}[b];
      map(.runs[]?.results[]? | . as $r | norm($r.level) as $lvl | select(ge($min; $lvl)) | {
        rule: (.ruleId // "unknown"),
        level: $lvl,
        file: (.locations[0].physicalLocation.artifactLocation.uri // "?"),
        line: (.locations[0].physicalLocation.region.startLine // 0),
        message: (.message.text // "")
      }) | add // []
    ' "${paths[@]}" > "$out_json"
    echo "Exported triage JSON: $out_json"
  else
    {
      echo '{"note":"Install jq for structured export","inputs":['
      i=0; for p in "${paths[@]}"; do
        (( i>0 )) && echo ","
        printf '  "%s"' "$p"
        ((i++))
      done
      echo
      echo ']}'
    } > "$out_json"
    echo "Exported placeholder JSON (jq not found): $out_json"
  fi

  if have jq && [[ "$FAIL_ON" != "none" ]]; then
    cnt=$(jq -r 'length' "$out_json" 2>/dev/null || echo 0)
    if [[ "$cnt" =~ ^[0-9]+$ ]] && (( cnt > 0 )); then
      log "Failing due to --fail-on=$FAIL_ON with $cnt findings"
      exit 3
    fi
  fi

  exit 0
fi

# ---- Step 1: Create DBs (optional) ----
# Ensure CodeQL is available for analysis actions only
have codeql || { log "ERROR: codeql not found in PATH. Install the CodeQL CLI and ensure 'codeql' is in PATH. See https://github.com/github/codeql-cli-binaries/releases"; exit 127; }

if (( CREATE_DBS )); then
  vlog "[1/3] Creating databases..."
  if [[ "$LANG_FILTER" == "js" || "$LANG_FILTER" == "all" ]]; then
    codeql database create "$DB_JS" --language=javascript --source-root "$REPO_ROOT" --overwrite
  fi
  if [[ "$LANG_FILTER" == "py" || "$LANG_FILTER" == "all" ]]; then
    codeql database create "$DB_PY" --language=python     --source-root "$REPO_ROOT" --overwrite
  fi
else
  vlog "[1/3] Skipping database creation; reusing: $DB_JS, $DB_PY"
  if [[ "$LANG_FILTER" == "js" || "$LANG_FILTER" == "all" ]]; then
    [[ -d "$DB_JS" ]] || { log "ERROR: Missing CodeQL DB: $DB_JS"; exit 1; }
  fi
  if [[ "$LANG_FILTER" == "py" || "$LANG_FILTER" == "all" ]]; then
    [[ -d "$DB_PY" ]] || { log "ERROR: Missing CodeQL DB: $DB_PY"; exit 1; }
  fi
fi

# ---- Step 2: Analyze ----
THREADS_ARG=()
if [[ "$THREADS" != "0" ]]; then THREADS_ARG+=("--threads=$THREADS"); fi

if [[ "$LANG_FILTER" == "js" || "$LANG_FILTER" == "all" ]]; then
  vlog "[2/3] Analyzing (JavaScript/TypeScript) with quality suite$([[ -n "$SUITE_SUFFIX" ]] && echo "+extended") ..."
  SARIF_JS="$OUT_DIR/codeql-js.sarif"
  ADDL_JS_ARGS=()
  if [[ -n "$SUITE_SUFFIX" ]]; then
    # When --extended is requested, include the extended suite via additional packs
    ADDL_JS_ARGS+=("--additional-packs=$JS_SUITE_EXTENDED")
  fi
  codeql database analyze "$DB_JS" "$JS_SUITE_QUALITY" \
    --format=sarifv2.1.0 --output "$SARIF_JS" \
    --verbosity=progress ${DOWNLOAD:+$DOWNLOAD} "${THREADS_ARG[@]}" "${ADDL_JS_ARGS[@]}"
fi

if [[ "$LANG_FILTER" == "py" || "$LANG_FILTER" == "all" ]]; then
  vlog "[2/3] Analyzing (Python) with quality suite$([[ -n "$SUITE_SUFFIX" ]] && echo "+extended") ..."
  SARIF_PY="$OUT_DIR/codeql-py.sarif"
  ADDL_PY_ARGS=()
  if [[ -n "$SUITE_SUFFIX" ]]; then
    ADDL_PY_ARGS+=("--additional-packs=$PY_SUITE_EXTENDED")
  fi
  codeql database analyze "$DB_PY" "$PY_SUITE_QUALITY" \
    --format=sarifv2.1.0 --output "$SARIF_PY" \
    --verbosity=progress ${DOWNLOAD:+$DOWNLOAD} "${THREADS_ARG[@]}" "${ADDL_PY_ARGS[@]}"
fi

# ---- Step 3: Summaries ----
vlog "[3/3] Summarizing results..."
summarize_sarif "$SARIF_JS"
summarize_sarif "$SARIF_PY"

echo
echo "Done. Full SARIF files:"
if [[ -n "${SARIF_JS:-}" ]]; then echo " - $SARIF_JS"; fi
if [[ -n "${SARIF_PY:-}" ]]; then echo " - $SARIF_PY"; fi

# Optionally open in viewer
if (( OPEN_VIEW )); then
  if have xdg-open; then
    if [[ -n "${SARIF_JS:-}" && -f "$SARIF_JS" ]]; then
      xdg-open "$SARIF_JS" >/dev/null 2>&1 || true
    fi
    if [[ -n "${SARIF_PY:-}" && -f "$SARIF_PY" ]]; then
      xdg-open "$SARIF_PY" >/dev/null 2>&1 || true
    fi
  else
    log "Note: xdg-open not found; skipping --open"
  fi
fi
