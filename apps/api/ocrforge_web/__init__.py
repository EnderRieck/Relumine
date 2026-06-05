from __future__ import annotations

import sys
from pathlib import Path

_CULTURECOURSE = Path(__file__).resolve().parents[3]
_SRC = _CULTURECOURSE / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

__version__ = "0.1.0"
