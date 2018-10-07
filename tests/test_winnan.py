"""Unit tests for the winnan/ package."""

from __future__ import absolute_import

import contextlib
import errno
import io
import os
import sys
import unittest

import test.support

if sys.platform in ("win32", "cygwin"):
    import winerror  # pylint: disable=import-error

from tests.context import winnan  # pylint: disable=wrong-import-position
from tests import test_flags  # pylint: disable=wrong-import-position
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

    def test_remove_while_io_open(self):  # pylint: disable=missing-docstring
        self._test_remove_while_open(io.open, expect_windows_failure=True)
        self._test_remove_while_open(winnan.io_open)

    def test_remove_while_open(self):  # pylint: disable=missing-docstring
        self._test_remove_while_open(open, expect_windows_failure=True)
        self._test_remove_while_open(winnan.open)

    def test_permission_bits(self):  # pylint: disable=missing-docstring
        def stat_new_file(open_func, **open_kwargs):
            """Creates a new file and returns the os.stat_result for it."""

            self.assertFalse(
                os.path.exists(test.support.TESTFN),
                "File leaked from earlier call to stat_new_file() function")

            with open_func(test.support.TESTFN, "w+", **open_kwargs) as fileobj:
                self.addCleanup(os.remove, test.support.TESTFN)
                stat_info = os.fstat(fileobj.fileno())

            self.doCleanups()
            return stat_info

        def compare_stat_infos(stat_info1, stat_info2):
            """Asserts the permission bits, user ids, and group ids of the os.stat_result instances
            are equal.
            """

            self.assertEqual(stat_info1.st_mode, stat_info2.st_mode)
            self.assertEqual(stat_info1.st_uid, stat_info2.st_uid)
            self.assertEqual(stat_info1.st_gid, stat_info2.st_gid)

        # Verify that the behavior matches the the built-in open() function.
        stat_info = stat_new_file(open)
        compare_stat_infos(stat_info, stat_new_file(winnan.open))
        compare_stat_infos(stat_info, stat_new_file(winnan.open, opener=None))
        compare_stat_infos(stat_info, stat_new_file(winnan.open, opener=winnan.os_open))

    def test_name_attribute(self):  # pylint: disable=missing-docstring
        with open(test.support.TESTFN, "w+"):
            self.addCleanup(os.remove, test.support.TESTFN)

        for mode in test_flags.TestModeToFlags.FLAGS_BY_MODE:
            if "x" in mode:
                # We skip testing all of the modes that contain the create flag here because the
                # file already exists.
                continue

            # We test winnan.open() with a variety of buffer sizes in order to exercise the
            # different possible return types of the function. Note that unbuffered I/O may only be
            # used in "binary" mode and line-buffered I/O may only be used in "text" mode.
            for buffering in (-1, 0 if "b" in mode else 1, 4096):
                # The name attribute of the returned file object should be whatever was specified to
                # winnan.open().
                with winnan.open(test.support.TESTFN, mode, buffering=buffering) as fileobj:
                    self.assertEqual(test.support.TESTFN, fileobj.name)

                    fileno = fileobj.fileno()
                    with winnan.open(fileno, mode, buffering=buffering, closefd=False) as fileobj2:
                        self.assertEqual(fileno, fileobj2.name)
                        self.assertEqual(fileno, fileobj2.fileno())
