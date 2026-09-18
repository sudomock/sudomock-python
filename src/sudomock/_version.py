"""Single source of the installed package version.

Read once from the distribution metadata (``pyproject.toml`` ``version``) so
``sudomock.__version__`` and the identity the SDK sends on every request can
never disagree.
"""

from __future__ import annotations

import importlib.metadata

try:
    __version__ = importlib.metadata.version("sudomock")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"
