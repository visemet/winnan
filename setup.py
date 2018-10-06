#!/usr/bin/env python
"""Setup script for the winnan package."""

import sys

import setuptools

SETUP_REQUIRES = []

if {"ptr", "pytest", "test"}.intersection(sys.argv):
    SETUP_REQUIRES.append("pytest-runner >= 4.2")

setuptools.setup(
    setup_requires=SETUP_REQUIRES,
)
