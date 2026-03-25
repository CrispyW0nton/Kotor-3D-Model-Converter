"""Enable running editors as a Python module.

Usage:
    python -m toolset.gui.editors --list
    python -m toolset.gui.editors --editor twoda
    python -m toolset.gui.editors --editor twoda myfile.2da
    python -m toolset.gui.editors myfile.utc --game-path "C:/Games/KOTOR"
    python -m toolset.gui.editors --editor nss --no-installation
"""
from __future__ import annotations

import sys

from toolset.gui.editors.standalone import main

if __name__ == "__main__":
    sys.exit(main())
