import sys
from pathlib import Path

# Add project root to sys.path so `import greenfield` works even if pytest
# sets the working dir to the tests package.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
