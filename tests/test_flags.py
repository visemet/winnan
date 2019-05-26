"""Unit tests for the winnan/flags.py module."""

from __future__ import absolute_import

import itertools
import os
import sys
import unittest

try:
    import fcntl
except ImportError:
    # The fcntl module isn't available on Windows.
    fcntl = None

import test.support

import pytest

from tests.context import winnan
import winnan.flags


class TestConstants(unittest.TestCase):
    """Unit tests for constants defined in the winnan/flags.py module."""

    def test_file_share_valid_flags_is_defined(self):  # pylint: disable=invalid-name,missing-docstring
        if sys.platform in ("win32", "cygwin"):
            self.assertNotEqual(0, winnan.flags.FILE_SHARE_VALID_FLAGS)
        else:
            self.assertEqual(0, winnan.flags.FILE_SHARE_VALID_FLAGS)

    def test_binary_is_defined(self):  # pylint: disable=missing-docstring
        if sys.platform in ("win32", "cygwin"):
            self.assertNotEqual(0, winnan.flags.O_BINARY)
        else:
            self.assertEqual(0, winnan.flags.O_BINARY)

    def test_noinherit_and_cloexec_are_defined(self):  # pylint: disable=invalid-name,missing-docstring
        self.assertNotEqual(0, winnan.flags.O_NOINHERIT)
        self.assertNotEqual(0, winnan.flags.O_CLOEXEC)
        self.assertEqual(winnan.flags.O_CLOEXEC, winnan.flags.O_NOINHERIT)

        if sys.platform not in ("win32", "cygwin") and sys.version_info >= (3, 3):
            self.assertEqual(os.O_CLOEXEC, winnan.flags.O_CLOEXEC)  # pylint: disable=no-member

    # The following test case was adapted from the test case added in
    # https://hg.python.org/cpython/rev/f1c544245eab.
    @unittest.skipUnless(fcntl, "requires fcntl module")
    def test_cloexec_sets_fd_cloexec_on_open(self):  # pylint: disable=invalid-name,missing-docstring
        with open(test.support.TESTFN, "w+"):
            self.addCleanup(os.remove, test.support.TESTFN)

        fd = os.open(test.support.TESTFN, os.O_RDONLY | winnan.flags.O_CLOEXEC)  # pylint: disable=invalid-name
        self.addCleanup(os.close, fd)

        self.assertTrue(fcntl.fcntl(fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC)


class TestModeToFlags(unittest.TestCase):
    """Unit tests for the mode_to_flags() function."""

    longMessage = True

    FLAGS_BY_MODE = {
        mode: flags
        for (modes, flags) in  (
            (("U", "rU", "bU", "tU", "rbU", "rtU", "r", "rb", "rt"), os.O_RDONLY),
            (("r+", "r+b", "r+t"), os.O_RDWR),
            (("w", "wb", "wt"),    os.O_CREAT  | os.O_TRUNC | os.O_WRONLY),  # pylint: disable=bad-whitespace
            (("w+", "w+b", "w+t"), os.O_CREAT  | os.O_TRUNC | os.O_RDWR),
            (("a", "ab", "at"),    os.O_APPEND | os.O_CREAT | os.O_WRONLY),  # pylint: disable=bad-whitespace
            (("a+", "a+b", "a+t"), os.O_APPEND | os.O_CREAT | os.O_RDWR),
            (("x", "xb", "xt"),    os.O_EXCL   | os.O_CREAT | os.O_WRONLY),  # pylint: disable=bad-whitespace
            (("x+", "x+b", "x+t"), os.O_EXCL   | os.O_CREAT | os.O_RDWR),
        )
        for mode in modes
    }  # yapf: disable

    def test_valid_modes(self):  # pylint: disable=missing-docstring
        for mode in self.FLAGS_BY_MODE:
            if sys.platform in ("win32", "cygwin"):
                expected_flags = (self.FLAGS_BY_MODE[mode] | winnan.flags.O_BINARY
                                  | winnan.flags.O_NOINHERIT)
            else:
                expected_flags = self.FLAGS_BY_MODE[mode] | winnan.flags.O_CLOEXEC

            actual_flags = winnan.flags.mode_to_flags(mode)
            self.assertEqual(expected_flags, actual_flags,
                             "flags for mode '%s' didn't match expected" % (mode))

    def test_invalid_modes(self):  # pylint: disable=missing-docstring
        with open(test.support.TESTFN, "w+"):
            self.addCleanup(os.remove, test.support.TESTFN)

        mode_chars = "xrwab+tUv"  # 'v' is an invalid mode, but that's the point.
        valid_modes = set("".join(sorted(mode)) for mode in self.FLAGS_BY_MODE)

        # Any mode of length >= 'max_mode_length' should be invalid.
        max_mode_length = 4
        self.assertGreater(max_mode_length, max(len(mode) for mode in valid_modes))

        for length in range(max_mode_length + 1):
            for mode in itertools.combinations_with_replacement(mode_chars, length):
                mode = "".join(sorted(mode))
                if mode in valid_modes:
                    continue

                with pytest.raises(ValueError):
                    winnan.flags.mode_to_flags(mode)
                    pytest.fail("Expected mode '%s' to raise an exception" % (mode))
