    #!/usr/bin/env bash
    set -euo pipefail
    #
    # ci_fetch_e2e_artifacts.sh
    # Fetch e2e job log and artifacts for a given GitHub Actions run/job, then parse JUnit failures.
    #
    # Requirements: GitHub CLI (`gh`), Python 3
    #
    usage() {
      cat <<'USAGE'
    Usage:
      ci_fetch_e2e_artifacts.sh --repo <owner/repo> --run-id <RUN_ID> --job-id <JOB_ID> [--out <dir>]

    Example:
      ci_fetch_e2e_artifacts.sh --repo Guffawaffle/LoquiLex --run-id 17691185152 --job-id 50284888074

    Notes:
      - Ensure `gh auth status` is authenticated for the repo.
      - Downloads ALL artifacts for the run into the output directory.
USAGE
}
REPO=""
    RUN_ID=""
    JOB_ID=""
    OUT_DIR=""

    while [[ $# -gt 0 ]]; do
      case "$1" in
        --repo) REPO="$2"; shift 2;;
        --run-id) RUN_ID="$2"; shift 2;;
        --job-id) JOB_ID="$2"; shift 2;;
        --out) OUT_DIR="$2"; shift 2;;
        -h|--help) usage; exit 0;;
        *) echo "Unknown arg: $1" >&2; usage; exit 1;;
      esac
    done

    if [[ -z "${REPO}" || -z "${RUN_ID}" || -z "${JOB_ID}" ]]; then
      echo "Missing required args." >&2
      usage
      exit 2
    fi

    if ! command -v gh >/dev/null 2>&1; then
      echo "Error: GitHub CLI (gh) not found. Install from https://cli.github.com/." >&2
      exit 3
    fi

    if [[ -z "${OUT_DIR}" ]]; then
      OUT_DIR=".artifacts/e2e-${RUN_ID}"
    fi

    mkdir -p "${OUT_DIR}"

    echo "==> Repo       : ${REPO}"
    echo "==> Run ID     : ${RUN_ID}"
    echo "==> Job ID     : ${JOB_ID}"
    echo "==> Output dir : ${OUT_DIR}"

    echo "==> Checking gh auth status..."
    gh auth status -R "${REPO}" || true

    echo "==> Fetching job log..."
    gh run view "${RUN_ID}" -R "${REPO}" --job "${JOB_ID}" --log > "${OUT_DIR}/e2e-job.log"
    echo "Saved: ${OUT_DIR}/e2e-job.log"

    echo "==> Downloading all artifacts for run..."
    gh run download "${RUN_ID}" -R "${REPO}" -D "${OUT_DIR}"
    echo "Artifacts downloaded into: ${OUT_DIR}"

    echo "==> Searching for JUnit XML files..."
    mapfile -t junit_files < <(find "${OUT_DIR}" -type f -iname "junit*e2e*.xml" -o -iname "*e2e*.xml" -o -iname "junit*.xml" 2>/dev/null | sort)

    if (( ${#junit_files[@]} == 0 )); then
      echo "No JUnit XMLs found. Will still summarize FAIL lines from job log."
    else
      echo "Found JUnit files:"
      printf '  - %s
' "${junit_files[@]}"
    fi

    echo "==> Parsing failures to summary..."
    python3 "$(dirname "$0")/parse_junit_failures.py" "${OUT_DIR}" > "${OUT_DIR}/e2e-failures-summary.txt" || true
    echo "Saved: ${OUT_DIR}/e2e-failures-summary.txt"

    echo "==> Done."
    echo "Inspect:"
    echo "  - ${OUT_DIR}/e2e-job.log"
    echo "  - ${OUT_DIR}/e2e-failures-summary.txt"
