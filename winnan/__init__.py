"""Replacement for open() allowing moving or unlinking before closing."""

from __future__ import absolute_import

from winnan.flags import (FILE_SHARE_VALID_FLAGS, O_BINARY, O_CLOEXEC, O_NOINHERIT)
from winnan.io_shim import open as io_open
from winnan.os_shim import open as os_open

try:
    from winnan._version import version as __version__
except ImportError:
    # The package is not installed so we don't bother giving it a version number.
    __version__ = None

open = io_open  # pylint: disable=redefined-builtin,invalid-name
