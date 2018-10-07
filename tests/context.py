"""Module that modifies Python's search path for modules in order to be able to import the winnan
package regardless of how the user has it installed.

See https://docs.python-guide.org/writing/structure/#test-suite for more details.
"""

from __future__ import absolute_import

import os.path
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import winnan  # pylint: disable=unused-import,wrong-import-position
