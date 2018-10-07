"""Replacement for os.open() allowing moving or unlinking before closing.

Adapted from the changes to Lib/share.py found in the https://bugs.python.org/file26249/share.patch
file that was uploaded to https://bugs.python.org/issue15244.

Copyright (c) 2012 Python Software Foundation; See THIRD-PARTY-NOTICES.

The following modifications were made to the original sources:
    - Add check for null byte in pathname as the path_converter() C function called by os.open()
      would have ordinarily been responsible for doing this.
    - Use constants from ntsecuritycon and win32file modules.
    - Use win32file.CreateFileW() function rather than _winapi module. This necessitated explicitly
      raising a FileExistsError exception when the file already exists.
"""

from __future__ import absolute_import

import errno
import os
import stat
import sys

if sys.platform in ("win32", "cygwin"):
    import msvcrt  # pylint: disable=import-error

    import ntsecuritycon  # pylint: disable=import-error
    import win32file  # pylint: disable=import-error
    import winerror  # pylint: disable=import-error

import winnan.flags  # pylint: disable=wrong-import-position

try:
    FileExistsError
except NameError:
    # The FileExistsError exception class was added in Python 3.3.
    FileExistsError = OSError  # pylint: disable=redefined-builtin

if sys.platform in ("win32", "cygwin"):
    _ACCESS_MASK = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
    _ACCESS_MAP = {
        os.O_RDONLY: win32file.GENERIC_READ,
        os.O_WRONLY: win32file.GENERIC_WRITE,
        os.O_RDWR:   win32file.GENERIC_READ | win32file.GENERIC_WRITE,
    }  # yapf: disable

    _CREATE_MASK = os.O_CREAT | os.O_EXCL | os.O_TRUNC
    _CREATE_MAP = {
        0:                                   win32file.OPEN_EXISTING,
        os.O_EXCL:                           win32file.OPEN_EXISTING,
        os.O_CREAT:                          win32file.OPEN_ALWAYS,
        os.O_CREAT | os.O_EXCL:              win32file.CREATE_NEW,
        os.O_CREAT | os.O_TRUNC | os.O_EXCL: win32file.CREATE_NEW,
        os.O_TRUNC:                          win32file.TRUNCATE_EXISTING,
        os.O_TRUNC | os.O_EXCL:              win32file.TRUNCATE_EXISTING,
        os.O_CREAT | os.O_TRUNC:             win32file.CREATE_ALWAYS,
    }  # yapf: disable

    def open(file, flags, mode=0o777, share_flags=None):  # pylint: disable=redefined-builtin,too-many-branches
        """Replacement for os.open() allowing moving or unlinking before closing."""
        if isinstance(file, bytes):
            file = file.decode("mbcs")

        if u"\0" in file:
            raise ValueError("embedded null character in path")

        if not isinstance(flags, int) and flags >= 0:
            raise ValueError("invalid flags: %r" % (flags, ))

        if not isinstance(mode, int) and mode >= 0:
            raise ValueError("invalid mode: %r" % (mode, ))

        if share_flags is None:
            share_flags = winnan.flags.FILE_SHARE_VALID_FLAGS

        if share_flags & ~winnan.flags.FILE_SHARE_VALID_FLAGS:
            raise ValueError("invalid share_flags: %r" % (share_flags, ))

        access_flags = _ACCESS_MAP[flags & _ACCESS_MASK]
        create_flags = _CREATE_MAP[flags & _CREATE_MASK]
        attrib_flags = win32file.FILE_ATTRIBUTE_NORMAL

        if flags & os.O_CREAT and mode & stat.S_IWRITE == 0:
            attrib_flags = win32file.FILE_ATTRIBUTE_READONLY

        if flags & os.O_TEMPORARY:  # pylint: disable=no-member
            share_flags |= win32file.FILE_SHARE_DELETE
            attrib_flags |= win32file.FILE_FLAG_DELETE_ON_CLOSE
            access_flags |= ntsecuritycon.DELETE

        if flags & os.O_SHORT_LIVED:  # pylint: disable=no-member
            attrib_flags |= win32file.FILE_ATTRIBUTE_TEMPORARY

        if flags & os.O_SEQUENTIAL:  # pylint: disable=no-member
            attrib_flags |= win32file.FILE_FLAG_SEQUENTIAL_SCAN

        if flags & os.O_RANDOM:  # pylint: disable=no-member
            attrib_flags |= win32file.FILE_FLAG_RANDOM_ACCESS

        try:
            handle = win32file.CreateFileW(file, access_flags, share_flags, None, create_flags,
                                           attrib_flags, None)
        except win32file.error as err:
            if err.winerror == winerror.ERROR_FILE_EXISTS:
                raise FileExistsError(errno.EEXIST, "File exists", file)

            raise

        return msvcrt.open_osfhandle(handle.Detach(), flags | winnan.flags.O_NOINHERIT)
else:

    def open(file, flags, mode=0o777, share_flags=None):  # pylint: disable=redefined-builtin,unused-argument
        """Wrapper around os.open() that ignores the 'share_flags' argument."""
        return os.open(file, flags | winnan.flags.O_CLOEXEC, mode)
