"""Canonical Ghost Studio split-source Python package.

Some domains are still owned by generated native payload copies while their
canonical ``src/`` restoration is in progress.  Add those payload source roots
to the package search path so normal repository imports resolve the same
cross-domain modules as the application without relying on pytest's conftest.
Canonical files under this directory remain first in resolution order. The
namespace extension also preserves source-mode startup when native package
roots have already been placed on ``sys.path``.
"""

from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

_repo_root = Path(__file__).resolve().parent.parent
for _payload_src in sorted((_repo_root / "native").glob("*/Python/src")):
    if not _payload_src.is_dir():
        continue
    _payload_path = str(_payload_src)
    if _payload_path not in __path__:
        __path__.append(_payload_path)
