"""Unit tests for the winnan/ package."""

from __future__ import absolute_import

import unittest

from tests.context import winnan  # pylint: disable=wrong-import-position
import winnan.flags  # pylint: disable=wrong-import-position


class BasicTestSuite(unittest.TestCase):
    """Unit tests for the winnan/ package."""

    def test_constants_defined(self):  # pylint: disable=missing-docstring
        self.assertEqual(winnan.flags.FILE_SHARE_VALID_FLAGS, winnan.FILE_SHARE_VALID_FLAGS)
        self.assertEqual(winnan.flags.O_BINARY, winnan.O_BINARY)
        self.assertEqual(winnan.flags.O_CLOEXEC, winnan.O_CLOEXEC)
        self.assertEqual(winnan.flags.O_NOINHERIT, winnan.O_NOINHERIT)
