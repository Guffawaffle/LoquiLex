#!/usr/bin/env bash
# dead-code-analysis.sh - Comprehensive dead code detection script
# Runs multiple tools to detect unused/dead code and generates reports

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Output directory for reports
REPORTS_DIR=".artifacts/dead-code-reports"
mkdir -p "$REPORTS_DIR"

echo "=== Dead Code Analysis Report ===" | tee "$REPORTS_DIR/summary.md"
echo "Generated: $(date)" | tee -a "$REPORTS_DIR/summary.md"
echo "" | tee -a "$REPORTS_DIR/summary.md"

# 1. Ruff - unused imports/variables/arguments
echo "## 1. Ruff Analysis (unused imports/variables/arguments)" | tee -a "$REPORTS_DIR/summary.md"
echo "" | tee -a "$REPORTS_DIR/summary.md"
if .venv/bin/python -m ruff check loquilex tests 2>&1 | tee "$REPORTS_DIR/ruff-unused.txt"; then
    echo "✅ No unused code detected by Ruff" | tee -a "$REPORTS_DIR/summary.md"
else
    echo "⚠️  Unused code detected by Ruff:" | tee -a "$REPORTS_DIR/summary.md"
    echo '```' | tee -a "$REPORTS_DIR/summary.md"
    cat "$REPORTS_DIR/ruff-unused.txt" | tee -a "$REPORTS_DIR/summary.md" 
    echo '```' | tee -a "$REPORTS_DIR/summary.md"
fi
echo "" | tee -a "$REPORTS_DIR/summary.md"

# 2. Vulture - dead code detection  
echo "## 2. Vulture Analysis (dead code detection, min-confidence 70%)" | tee -a "$REPORTS_DIR/summary.md"
echo "" | tee -a "$REPORTS_DIR/summary.md"
if .venv/bin/python -m vulture loquilex --min-confidence 70 2>&1 | tee "$REPORTS_DIR/vulture-deadcode.txt"; then
    echo "✅ No dead code detected by Vulture" | tee -a "$REPORTS_DIR/summary.md"
else
    echo "⚠️  Dead code detected by Vulture:" | tee -a "$REPORTS_DIR/summary.md"
    echo '```' | tee -a "$REPORTS_DIR/summary.md"
    cat "$REPORTS_DIR/vulture-deadcode.txt" | tee -a "$REPORTS_DIR/summary.md"
    echo '```' | tee -a "$REPORTS_DIR/summary.md"
fi
echo "" | tee -a "$REPORTS_DIR/summary.md"

# 3. Coverage analysis - 0% coverage files
echo "## 3. Coverage Analysis (files with 0% coverage)" | tee -a "$REPORTS_DIR/summary.md"
echo "" | tee -a "$REPORTS_DIR/summary.md"
echo "Running coverage analysis..." | tee -a "$REPORTS_DIR/summary.md"

# Run tests with coverage
.venv/bin/python -m pytest --cov=loquilex --cov-report=term-missing --cov-report=html -q > "$REPORTS_DIR/coverage-output.txt" 2>&1

# Extract 0% coverage files
echo "Files with 0% coverage:" | tee -a "$REPORTS_DIR/summary.md"
echo '```' | tee -a "$REPORTS_DIR/summary.md"
if grep "   0%" "$REPORTS_DIR/coverage-output.txt" > "$REPORTS_DIR/zero-coverage.txt" 2>/dev/null; then
    cat "$REPORTS_DIR/zero-coverage.txt" | tee -a "$REPORTS_DIR/summary.md"
else
    echo "✅ No files with 0% coverage found" | tee -a "$REPORTS_DIR/summary.md"
fi
echo '```' | tee -a "$REPORTS_DIR/summary.md"
echo "" | tee -a "$REPORTS_DIR/summary.md"

# 4. Low coverage files (under 25%)
echo "Files with <25% coverage:" | tee -a "$REPORTS_DIR/summary.md"  
echo '```' | tee -a "$REPORTS_DIR/summary.md"
# Extract lines with coverage percentage and filter for <25%
if grep -E "^\S+\s+\d+\s+\d+\s+([0-9]|1[0-9]|2[0-4])%\s" "$REPORTS_DIR/coverage-output.txt" > "$REPORTS_DIR/low-coverage.txt" 2>/dev/null; then
    cat "$REPORTS_DIR/low-coverage.txt" | tee -a "$REPORTS_DIR/summary.md"
else
    echo "✅ No files with <25% coverage found" | tee -a "$REPORTS_DIR/summary.md"
fi  
echo '```' | tee -a "$REPORTS_DIR/summary.md"
echo "" | tee -a "$REPORTS_DIR/summary.md"

# 5. Multi-signal analysis - items flagged by ≥2 tools
echo "## 4. Multi-Signal Analysis (flagged by ≥2 tools)" | tee -a "$REPORTS_DIR/summary.md"
echo "" | tee -a "$REPORTS_DIR/summary.md"

# Create consolidated analysis
echo "Analyzing overlap between tools..." | tee -a "$REPORTS_DIR/summary.md"

# Extract specific issues from each tool and cross-reference
echo "### Files/functions mentioned by multiple tools:" | tee -a "$REPORTS_DIR/summary.md"
echo '```' | tee -a "$REPORTS_DIR/summary.md"

# Check for overlap between Ruff and Vulture findings
if [ -s "$REPORTS_DIR/ruff-unused.txt" ] && [ -s "$REPORTS_DIR/vulture-deadcode.txt" ]; then
    echo "Cross-referencing Ruff and Vulture findings..." | tee -a "$REPORTS_DIR/summary.md"
    
    # Extract file paths and variable names from both reports for comparison
    grep -o "[a-zA-Z_/][a-zA-Z0-9_/]*\.py" "$REPORTS_DIR/ruff-unused.txt" | sort -u > "$REPORTS_DIR/ruff-files.tmp" 2>/dev/null || true
    grep -o "[a-zA-Z_/][a-zA-Z0-9_/]*\.py" "$REPORTS_DIR/vulture-deadcode.txt" | sort -u > "$REPORTS_DIR/vulture-files.tmp" 2>/dev/null || true
    
    if [ -s "$REPORTS_DIR/ruff-files.tmp" ] && [ -s "$REPORTS_DIR/vulture-files.tmp" ]; then
        comm -12 "$REPORTS_DIR/ruff-files.tmp" "$REPORTS_DIR/vulture-files.tmp" > "$REPORTS_DIR/common-files.tmp"
        if [ -s "$REPORTS_DIR/common-files.tmp" ]; then
            echo "🎯 Files flagged by both Ruff and Vulture:" | tee -a "$REPORTS_DIR/summary.md"
            cat "$REPORTS_DIR/common-files.tmp" | tee -a "$REPORTS_DIR/summary.md"
        fi
    fi
    
    # Cleanup temp files
    rm -f "$REPORTS_DIR"/*.tmp
else
    echo "No overlap analysis possible (insufficient data from tools)" | tee -a "$REPORTS_DIR/summary.md"
fi

echo '```' | tee -a "$REPORTS_DIR/summary.md"
echo "" | tee -a "$REPORTS_DIR/summary.md"

# 6. Summary and recommendations
echo "## 5. Summary & Recommendations" | tee -a "$REPORTS_DIR/summary.md"
echo "" | tee -a "$REPORTS_DIR/summary.md"

ruff_count=$(wc -l < "$REPORTS_DIR/ruff-unused.txt" 2>/dev/null || echo "0")
vulture_count=$(wc -l < "$REPORTS_DIR/vulture-deadcode.txt" 2>/dev/null || echo "0")
zero_cov_count=$(wc -l < "$REPORTS_DIR/zero-coverage.txt" 2>/dev/null || echo "0")

echo "- **Ruff findings**: $ruff_count unused imports/variables/arguments" | tee -a "$REPORTS_DIR/summary.md"
echo "- **Vulture findings**: $vulture_count dead code items" | tee -a "$REPORTS_DIR/summary.md"  
echo "- **Zero coverage files**: $zero_cov_count files" | tee -a "$REPORTS_DIR/summary.md"
echo "" | tee -a "$REPORTS_DIR/summary.md"

if [ "$ruff_count" -gt 0 ] || [ "$vulture_count" -gt 0 ] || [ "$zero_cov_count" -gt 0 ]; then
    echo "**Next Steps:**" | tee -a "$REPORTS_DIR/summary.md"
    echo "1. Review items flagged by multiple tools for removal" | tee -a "$REPORTS_DIR/summary.md" 
    echo "2. Unused function parameters can often be prefixed with _ if they're required by interface" | tee -a "$REPORTS_DIR/summary.md"
    echo "3. Dead code items with high confidence (>90%) are safe candidates for removal" | tee -a "$REPORTS_DIR/summary.md"
    echo "4. Low/zero coverage files should be examined for actual usage vs dead code" | tee -a "$REPORTS_DIR/summary.md"
else
    echo "✅ **No significant dead code detected!** Repository appears clean." | tee -a "$REPORTS_DIR/summary.md"
fi

echo "" | tee -a "$REPORTS_DIR/summary.md"
echo "Full reports saved to: $REPORTS_DIR/" | tee -a "$REPORTS_DIR/summary.md"

echo ""
echo "=== Analysis Complete ==="
echo "Summary report: $REPORTS_DIR/summary.md"
echo "Individual reports: $REPORTS_DIR/"