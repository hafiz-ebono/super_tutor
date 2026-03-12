"""
Root conftest for the backend test suite.

Adds backend/ to sys.path so `from app.xxx import ...` works whether
pytest is invoked from backend/ directly or from the monorepo root
(e.g. via VSCode's test runner).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
