"""Module that provides utility functions for marking unit tests."""

from __future__ import absolute_import

import unittest


def skip_unless_winnan_or(condition, reason):
    """Skip a test unless it is for the winnan/ package or the condition is true."""

    def decorator(func):  # pylint: disable=missing-docstring
        def decorated(self, *args, **kwargs):  # pylint: disable=missing-docstring
            if self.__class__.__name__.startswith("Winnan") or condition:
                return func(self, *args, **kwargs)

            raise unittest.SkipTest(reason)

        return decorated

    return decorator
