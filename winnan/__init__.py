"""Replacement for open() allowing moving or unlinking before closing."""

from __future__ import absolute_import

from winnan.flags import (FILE_SHARE_VALID_FLAGS, O_BINARY, O_CLOEXEC, O_NOINHERIT)
