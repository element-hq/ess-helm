import sys
from pathlib import Path

import typer

HERE = Path(__file__).resolve().parent


def run_tests():
    def _run_tests(additional_test_value_file: str | None = None):
        import pytest

        errcode = pytest.main([str(HERE)] + sys.argv[1:])
        sys.exit(errcode)

    typer.run(_run_tests())


def setup_cluster():
    import os

    import pytest

    os.environ["PYTEST_KEEP_CLUSTER"] = "1"
    errcode = pytest.main([str(HERE)] + ["--env-setup"])
    sys.exit(errcode)
