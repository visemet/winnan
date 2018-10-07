#!/usr/bin/env python
"""Setup script for the winnan package."""

import distutils.errors  # pylint: disable=import-error,no-name-in-module
import distutils.log  # pylint: disable=import-error,no-name-in-module
import sys

import setuptools


class FormatCode(setuptools.Command):
    """Command to run yapf on all Python code."""

    user_options = []

    def initialize_options(self):  # pylint: disable=missing-docstring
        pass

    def finalize_options(self):  # pylint: disable=missing-docstring
        pass

    def run(self):  # pylint: disable=missing-docstring
        import yapf  # pylint: disable=import-error

        try:
            yapf.main([
                None,
                "--in-place",
                "--recursive",
                "--verbose",
                "setup.py",
                "tests/",
                "winnan/",
            ])
        except yapf.errors.YapfError as err:
            msg = "yapf: {}".format(err)
            self.announce(msg, distutils.log.ERROR)  # pylint: disable=no-member
            raise distutils.errors.DistutilsError(msg)  # pylint: disable=no-member


SETUP_REQUIRES = []

if {"ptr", "pytest", "test"}.intersection(sys.argv):
    SETUP_REQUIRES.append("pytest-runner >= 4.2")

if {"format"}.intersection(sys.argv):
    SETUP_REQUIRES.append("yapf == 0.25.0")

setuptools.setup(
    setup_requires=SETUP_REQUIRES,
    cmdclass=dict(format=FormatCode),
)
