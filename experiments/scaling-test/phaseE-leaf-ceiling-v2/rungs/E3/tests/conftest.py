# Parent-owned. Puts the project root on sys.path so tests and the
# umbrella can `import catalog`, `import discounts`, `import engine`,
# `import validation`, `import currency`, `import shipping`, `import
# notifications` directly — the impl modules live at repo root, matching
# MODULES.md's bare module names (mirrors the proven layout used in
# phaseD-fix-verification/run-3: root-level impl files, contract kept
# under src/ with a name that never shadows a stdlib module).
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
