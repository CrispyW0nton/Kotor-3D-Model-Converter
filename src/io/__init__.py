"""Optional external file-format bridges for GhostRigger.

Core IO is split between canonical repository sources and package-local
embedded adapters.  Extending the package path lets both owners participate
without copying adapter-only modules into the root source tree.
"""

from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)
