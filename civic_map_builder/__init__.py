"""
Top-level package for civic-map-builder.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("civic-map-builder")
except PackageNotFoundError:  # pragma: no cover - during editable installs
    __version__ = "0.0.0"
