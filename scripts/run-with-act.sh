#!/bin/bash
# run-with-act.sh - Use Act to run GitHub Actions locally

echo "=== Running CI with Act (GitHub Actions locally) ==="

if ! command -v act &> /dev/null; then
    echo "Act not installed. Install with:"
    echo "# On macOS:"
    echo "brew install act"
    echo ""
    echo "# On Linux:"
    echo "curl https://raw.githubusercontent.com/nektos/act/master/install.sh | bash"
    echo ""
    echo "# Or download from: https://github.com/nektos/act/releases"
    exit 1
fi

echo "Running all CI jobs locally..."
act

# Or run specific jobs:
# act -j lint      # Just lint
# act -j unit      # Just unit tests
# act -j e2e       # Just e2e tests