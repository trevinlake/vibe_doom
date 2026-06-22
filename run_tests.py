#!/usr/bin/env python3
"""Convenience runner: discovers and runs the whole unit-test suite.

    python run_tests.py            # all tests
    python -m unittest -v          # equivalent, more verbose

Exits non-zero if anything fails, so it is CI-friendly.
"""

import sys
import unittest


def main():
    loader = unittest.TestLoader()
    suite = loader.discover("tests")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
