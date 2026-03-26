import sys
from pathlib import Path
from typing import Annotated, Literal

import typer

HERE = Path(__file__).resolve().parent

existing_test_suites = [file.stem for file in (HERE / "env").glob("*.rc")]


def run_tests():
    def _run_tests(
        test_suite: Annotated[Literal[*existing_test_suites], typer.Option()],
        additional_test_values_file: str | None = None,
        args: Annotated[list[str] | None, typer.Argument(allow_dash=True)] = None,
    ):
        import os

        import pytest
        from dotenv import load_dotenv

        if not args:
            args = []

        test_suite_rc = HERE / "env" / f"{test_suite}.rc"
        load_dotenv(test_suite_rc)

        if additional_test_values_file:
            os.environ["ADDITIONAL_TEST_VALUES_FILE"] = additional_test_values_file

        errcode = pytest.main([str(HERE)] + args)
        sys.exit(errcode)

    typer.run(_run_tests)


def setup_cluster():
    import os

    import pytest

    os.environ["PYTEST_KEEP_CLUSTER"] = "1"
    errcode = pytest.main([str(HERE)] + ["--env-setup"])
    sys.exit(errcode)
