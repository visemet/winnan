"""Module that provides utility functions and constants for opening files."""

from __future__ import absolute_import

import os
import sys

try:
    basestring
except NameError:
    basestring = (str, bytes)  # pylint: disable=redefined-builtin,invalid-name

if sys.platform in ("win32", "cygwin"):
    import win32file  # pylint: disable=import-error

    FILE_SHARE_VALID_FLAGS = (win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE
                              | win32file.FILE_SHARE_DELETE)
    O_BINARY = os.O_BINARY  # pylint: disable=no-member
    O_NOINHERIT = O_CLOEXEC = os.O_NOINHERIT  # pylint: disable=no-member
else:
    import winnan._cython.fcntl as winnan_fcntl

    FILE_SHARE_VALID_FLAGS = 0
    O_BINARY = 0
    O_NOINHERIT = O_CLOEXEC = winnan_fcntl.O_CLOEXEC


def mode_to_flags(mode):  # pylint: disable=too-many-branches
    """Converts the string 'mode' to the flags constants for use with the os.open() function.

    Adapted from the FileIO.__init__() function found in Lib/_pyio.py of Python 3.7.0.
    Copyright (c) 2015-2018 Python Software Foundation; See THIRD-PARTY-NOTICES.

    The following modifications were made to the original sources:
        - Changed to permit modes "t" and "U".
        - Added error checking for mode "U" that isn't present in Python 2.
        - Changed to use O_CLOEXEC constant as defined by the winnan_fcntl Cython module.
    """
    if not isinstance(mode, basestring):
        raise TypeError("invalid mode: %s" % (mode, ))

    modes = set(mode)

    # We must permit the modes "t" and "U" even though they don't impact the returned flags because
    # 'mode' may come from a caller that io.open() hasn't already filtered.
    if modes - set("xrwab+tU") or len(modes) < len(mode):
        raise ValueError("invalid mode: %s" % (mode, ))

    if "U" in mode:
        if sum(c in "xwa+" for c in mode) != 0:
            # Python 2.7 doesn't check if mode U is used in combination in with 'x' or '+', so we do
            # it here ourselves. See https://bugs.python.org/issue2091 for more details.
            raise ValueError("mode U cannot be combined with 'x', 'w', 'a', or '+'")
    elif sum(c in "xrwa" for c in mode) != 1 or mode.count("+") > 1:
        raise ValueError(
            "Must have exactly one of create/read/write/append mode and at most one plus")

    if sum(c in "bt" for c in mode) == 2:
        raise ValueError("can't have text and binary mode at once")

    readable = False
    writable = False

    if "x" in mode:
        writable = True
        flags = os.O_EXCL | os.O_CREAT
    elif "r" in mode or "U" in mode:
        readable = True
        flags = 0
    elif "w" in mode:
        writable = True
        flags = os.O_CREAT | os.O_TRUNC
    elif "a" in mode:
        writable = True
        flags = os.O_APPEND | os.O_CREAT

    if "+" in mode:
        readable = True
        writable = True

    if readable and writable:
        flags |= os.O_RDWR
    elif readable:
        flags |= os.O_RDONLY
    else:
        flags |= os.O_WRONLY

    flags |= O_BINARY
    flags |= O_NOINHERIT

    return flags
