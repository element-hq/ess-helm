import sys
from pathlib import Path

import typer

HERE = Path(__file__).resolve().parent


def run_tests():
    def _run_tests(additional_test_values_file: str | None = None):
        import os

        import pytest

        argv_base_index = 1
        if additional_test_values_file:
            os.environ["ADDITIONAL_TEST_VALUES_FILE"] = additional_test_values_file
            argv_base_index += 2

        errcode = pytest.main([str(HERE)] + sys.argv[argv_base_index:])
        sys.exit(errcode)

    typer.run(_run_tests)


def setup_cluster():
    import os

    import pytest

    os.environ["PYTEST_KEEP_CLUSTER"] = "1"
    errcode = pytest.main([str(HERE)] + ["--env-setup"])
    sys.exit(errcode)
