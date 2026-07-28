"""KotOR module loading, hydration, inspection, packaging, and saving.

The native payload remains the compatibility source for canonical modules that
have not yet been restored under ``src/``.  Extending this package path keeps a
plain repository import honest: restored source modules load from ``src/``,
while their still-payload-owned siblings resolve without pytest/conftest path
injection.  Packaged native copies do not have the repository-relative payload
directory, so the bridge is inert inside the embedded runtime.
"""

from pathlib import Path

_payload_modules = (
    Path(__file__).resolve().parents[3]
    / "native"
    / "GhostRigger.Core.Scene"
    / "Python"
    / "src"
    / "core"
    / "modules"
)
if _payload_modules.is_dir():
    _payload_path = str(_payload_modules)
    if _payload_path not in __path__:
        __path__.append(_payload_path)
