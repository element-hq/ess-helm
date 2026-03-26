import sys
from pathlib import Path
from typing import Annotated, Literal

import typer

HERE = Path(__file__).resolve().parent

existing_test_suites = [file.stem for file in (HERE / "env").glob("*.rc")]


def run_tests():
    def _run_tests(
        test_suite: Annotated[Literal[*existing_test_suites], typer.Option()],
        pull_chart: bool = False,
        chart_version: str | None = None,
        keep: bool = False,
        additional_test_values_file: str | None = None,
        args: Annotated[list[str] | None, typer.Argument(allow_dash=True)] = None,
    ):
        import os
        import subprocess
        from importlib.metadata import version

        import pytest
        import semver
        import yaml
        from dotenv import load_dotenv

        __version__ = version("mypackage")
        if not args:
            args = []

        if pull_chart:
            if not chart_version:
                # We pull the chart version depending on the python package version as those are synchronized
                if semver.Version.is_valid(__version__):
                    chart_version = __version__
                else:
                    raise ValueError("--chart-version must be provided when pulling chart against a development build")

            Path("charts").mkdir(exist_ok=True)

            # Call helm pull to get the latest chart version
            subprocess.run(
                ["helm", "pull", f"oci://ghcr.io/element-hq/ess-helm/matrix-stack:{chart_version}"],
                check=True,
            )

            subprocess.run(["tar", "xvf", f"matrix-stack-{chart_version}.tgz", "-C", "charts"])

        if chart_version:
            with open("charts/matrix-stack/Chart.yaml") as f:
                chart_yaml = yaml.safe_load(f)
                if chart_yaml["version"] != chart_version:
                    raise ValueError(
                        f"Chart version {chart_yaml['version']} does not match "
                        f"expected required version {chart_version}. "
                        "Maybe you want to pull with --pull-chart?"
                    )

        test_suite_rc = HERE / "env" / f"{test_suite}.rc"
        load_dotenv(test_suite_rc)

        if keep:
            os.environ["PYTEST_KEEP_CLUSTER"] = "1"

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
