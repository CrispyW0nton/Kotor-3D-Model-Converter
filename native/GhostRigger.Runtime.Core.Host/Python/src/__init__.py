"""GhostRigger split-source namespace package.

The native Visual Studio layout stores Python modules across many
``native/GhostRigger.*/Python`` roots.  Keep this package namespace-compatible
so source-mode startup can merge those roots the same way the embedded payload
importer does in packaged builds.
"""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
