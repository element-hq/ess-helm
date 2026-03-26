import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_tests():

    import pytest

    errcode = pytest.main([HERE] + sys.argv[1:])
    sys.exit(errcode)


def setup_cluster():
    import os

    import pytest

    os.environ["PYTEST_KEEP_CLUSTER"] = "1"
    errcode = pytest.main([HERE] + ["--env-setup"])
    sys.exit(errcode)
