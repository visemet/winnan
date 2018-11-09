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


class LintCode(setuptools.Command):
    """Command to run pylint on all Python code."""

    user_options = []

    def initialize_options(self):  # pylint: disable=missing-docstring
        pass

    def finalize_options(self):  # pylint: disable=missing-docstring
        pass

    def run(self):  # pylint: disable=missing-docstring,no-self-use
        import pylint.lint  # pylint: disable=import-error

        pylint.lint.Run(["setup.py", "tests/", "winnan/"], exit=False)


SETUP_REQUIRES = []
CYTHON_EXTENSION_MODULES = []

if sys.platform not in ("win32", "cygwin"):
    SETUP_REQUIRES.append("Cython >= 0.29.1")
    CYTHON_EXTENSION_MODULES += [
        setuptools.Extension("winnan._cython.fcntl", ["winnan/_cython/fcntl.pyx"]),
    ]

if {"ptr", "pytest", "test"}.intersection(sys.argv):
    SETUP_REQUIRES.append("pytest-runner >= 4.2")

if {"format"}.intersection(sys.argv):
    SETUP_REQUIRES.append("yapf == 0.25.0")

if {"lint"}.intersection(sys.argv):
    SETUP_REQUIRES.append("pylint == 1.9.3")

setuptools.setup(
    ext_modules=CYTHON_EXTENSION_MODULES,
    setup_requires=SETUP_REQUIRES,
    cmdclass=dict(format=FormatCode, lint=LintCode),
)
