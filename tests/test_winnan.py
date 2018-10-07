"""Unit tests for the winnan/ package."""

from __future__ import absolute_import

import contextlib
import errno
import os
import sys
import unittest

import test.support

if sys.platform in ("win32", "cygwin"):
    import winerror  # pylint: disable=import-error

from tests.context import winnan  # pylint: disable=wrong-import-position
import winnan.flags  # pylint: disable=wrong-import-position


class BasicTestSuite(unittest.TestCase):
    """Unit tests for the winnan/ package."""

    def test_constants_defined(self):  # pylint: disable=missing-docstring
        self.assertEqual(winnan.flags.FILE_SHARE_VALID_FLAGS, winnan.FILE_SHARE_VALID_FLAGS)
        self.assertEqual(winnan.flags.O_BINARY, winnan.O_BINARY)
        self.assertEqual(winnan.flags.O_CLOEXEC, winnan.O_CLOEXEC)
        self.assertEqual(winnan.flags.O_NOINHERIT, winnan.O_NOINHERIT)

    def _test_remove_while_open(self, opener, expect_windows_failure=False):
        def force_remove(filename):
            """Remove the file if it exists and suppress errors if it doesn't."""
            try:
                os.remove(filename)
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise

        with opener(test.support.TESTFN, "w+"):
            self.addCleanup(force_remove, test.support.TESTFN)

            if sys.platform in ("win32", "cygwin") and expect_windows_failure:
                with self.assertRaises(WindowsError) as cm:  # pylint: disable=invalid-name,undefined-variable
                    os.remove(test.support.TESTFN)

                self.assertEqual(winerror.ERROR_SHARING_VIOLATION, cm.exception.winerror)
                self.assertEqual(
                    "The process cannot access the file because it is being used by another"
                    " process", cm.exception.strerror)
                self.assertEqual(test.support.TESTFN, cm.exception.filename)
            else:
                os.remove(test.support.TESTFN)

        self.doCleanups()

    def test_remove_while_os_open(self):  # pylint: disable=missing-docstring
        def make_opener(os_open_func):
            """Return a context manager that acquires a file descriptor using the os_open_func()
            function and closes it using os.close().
            """

            @contextlib.contextmanager
            def os_closing(filename, mode):  # pylint: disable=missing-docstring
                fd = os_open_func(filename, winnan.flags.mode_to_flags(mode))  # pylint: disable=invalid-name
                try:
                    yield fd
                finally:
                    os.close(fd)

            return os_closing

        self._test_remove_while_open(make_opener(os.open), expect_windows_failure=True)
        self._test_remove_while_open(make_opener(winnan.os_open))
