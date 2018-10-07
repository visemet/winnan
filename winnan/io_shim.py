"""Replacement for io.open() allowing moving or unlinking before closing."""

from __future__ import absolute_import

import io
import os
import sys

import winnan.flags
import winnan.os_shim

try:
    basestring
except NameError:
    basestring = (str, bytes)  # pylint: disable=redefined-builtin,invalid-name

try:
    long
except NameError:
    integer_types = (int, )  # pylint: disable=invalid-name
else:
    integer_types = (int, long)  # pylint: disable=invalid-name


# pylint: disable=redefined-builtin,too-many-arguments
def open(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, closefd=True,
         opener=None, opener_mode=0o666, share_flags=None):
    """Replacement for io.open() allowing moving or unlinking before closing.

    The custom opener() function must accept 'mode' and 'share_flags' keyword arguments. Calling
    opener(file, flags, mode=opener_mode, share_flags=share_flags) should return an open file
    descriptor. Specifying 'winnan.os_open' as the opener() function results in functionality
    identical to specifying None.
    """

    if sys.version_info >= (3, 6) and not isinstance(file, integer_types):
        file = os.fspath(file)  # pylint: disable=no-member

    if not isinstance(file, (basestring, integer_types)):
        raise TypeError("invalid file: %r" % (file, ))

    if isinstance(file, integer_types):
        fd = file  # pylint: disable=invalid-name
    else:
        if not closefd:
            raise ValueError("Cannot use closefd=False with file name")

        flags = winnan.flags.mode_to_flags(mode)

        if opener is None:
            opener = winnan.os_shim.open

        fd = opener(file, flags, mode=opener_mode, share_flags=share_flags)  # pylint: disable=invalid-name

    # io.open() takes responsibility for closing 'fd' when closefd=True. This means for all cases
    # where winnan.io_shim.open() had opened the file descriptor that io.open() is responsible for
    # cleaning it up if anything goes wrong.
    fileobj = io.open(fd, mode=mode, buffering=buffering, encoding=encoding, errors=errors,
                      newline=newline, closefd=closefd)

    # We overwrite the 'name' attribute of the FileIO instance to be the original 'file' argument to
    # simulate io.open()'s behavior had it been called with the filename and 'opener' as its
    # arguments.
    if not buffering:
        # When using unbuffered I/O, io.open() returns a FileIO instance. Unbuffered I/O can only be
        # used with "binary" mode and not with "text" mode.
        fileobj.name = file
    elif "b" in mode:
        # When using "binary" mode and buffered I/O, io.open() returns a BufferedReader,
        # BufferedWriter, or BufferedRandom instance that wraps a FileIO instance.
        fileobj.raw.name = file
    else:
        # When using "text" mode and buffered I/O, io.open() returned a TextIOWrapper instance that
        # wraps a BufferedReader, BufferedWriter, or BufferedRandom instance that wraps a FileIO
        # instance.
        fileobj.buffer.raw.name = file

    return fileobj
