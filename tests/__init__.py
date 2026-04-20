"""GhostRigger test package.

Phase G3 guard-rail tests and live-model regression suites.  See the individual
``test_*.py`` modules for scope.  All tests are designed to run from the repo
root with either:

    python -m unittest tests.test_<name>
    python tests/test_<name>.py

and they self-configure ``sys.path`` so no ``PYTHONPATH`` gymnastics are
required.
"""
