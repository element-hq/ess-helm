# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import subprocess
import sys
from pathlib import Path
from typing import Annotated, Literal

import typer
import yaml

HERE = Path(__file__).resolve().parent

existing_test_suites = [file.stem for file in (HERE / "env").glob("*.rc")]


def run_command(cmd, check=True):
    result = subprocess.run(cmd, shell=True, check=check, text=True, capture_output=True)
    return result.stdout


def run_command_to_file(cmd, output_file, check=True, text=True):
    """Run a command and write its output directly to a file."""
    with open(output_file, "w") as f:
        f.write("----\n")
        subprocess.run(cmd, shell=True, check=check, stdout=f, stderr=subprocess.STDOUT, text=text)


def is_k3d_running():
    """Tell if the k3d ess-helm cluster server container is running."""
    result = subprocess.run(
        "docker inspect --format '{{.State.Running}}' k3d-ess-helm-server-0",
        shell=True,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def export_docker_containers(destination: Path):
    """Write the logs and the inspect content of every container attached to the k3d network."""
    destination.mkdir(exist_ok=True)
    containers = run_command(
        "docker ps -a --filter network=k3d-ess-helm --format '{{.Names}}'", check=False
    ).splitlines()
    for container in containers:
        # docker logs fails on containers that never started, so we ignore errors
        run_command_to_file(f"docker logs {container}", destination / f"{container}.logs", check=False)
        run_command_to_file(f"docker inspect {container}", destination / f"{container}.inspect.json", check=False)


def censor_secrets_yaml(yaml_content):
    """Censor all data and stringData fields in a Kubernetes secrets YAML."""
    secrets = yaml.safe_load(yaml_content)
    if secrets and "items" in secrets:
        for item in secrets["items"]:
            if "data" in item:
                for key in item["data"]:
                    item["data"][key] = "censored"
            if "stringData" in item:
                for key in item["stringData"]:
                    item["stringData"][key] = "censored"
    return yaml.dump(secrets, default_flow_style=False)


def collect_ess_logs():
    def _collect_logs(destination: Path = Path("ess-helm-logs"), system_logs: bool = False):
        Path(destination).mkdir(exist_ok=True)

        if system_logs:
            # Get logs and inspect content of all containers attached to the k3d network
            export_docker_containers(destination / "docker")

        if not is_k3d_running():
            typer.echo(
                "Warning: the k3d ess-helm cluster is not running. Skipping the collection of the Kubernetes resources."
            )
            typer.echo(f"Logs and resources collected in {destination}")
            return

        # Merge kubeconfig
        subprocess.run("k3d kubeconfig merge ess-helm -ds", shell=True, check=True)

        # Get all namespaces
        namespaces = run_command(
            "kubectl --context k3d-ess-helm get ns -o custom-columns=NS:.metadata.name --no-headers"
        ).splitlines()

        resources = [
            "pods",
            "deployments",
            "statefulsets",
            "services",
            "configmaps",
            "ingresses",
            "persistentvolumes",
            "persistentvolumeclaims",
            "endpoints",
        ]

        for ns in namespaces:
            if not system_logs and "ess" not in ns:
                continue
            (destination / ns).mkdir(exist_ok=True)
            # Get all pods in the namespace
            pods = run_command(
                f"kubectl --context=k3d-ess-helm get pods -n {ns} -o custom-columns=NAME:.metadata.name --no-headers"
            ).splitlines()

            for pod in pods:
                # Get previous logs
                run_command_to_file(
                    f"kubectl --context=k3d-ess-helm -n {ns} logs --all-containers --prefix --timestamps "
                    f"--ignore-errors --previous {pod}",
                    f"{destination}/{ns}/{pod}.previous",
                    check=False,
                )
                # Get current logs
                run_command_to_file(
                    f"kubectl --context=k3d-ess-helm -n {ns} logs --all-containers --prefix --timestamps "
                    f"--ignore-errors {pod}",
                    f"{destination}/{ns}/{pod}.logs",
                    check=False,
                )

            # Get resources
            for resource in resources:
                output_file_prefix = f"{destination}/{ns}/{resource}"
                run_command_to_file(
                    f"kubectl --context=k3d-ess-helm get {resource} -n {ns}", f"{output_file_prefix}.txt"
                )
                run_command_to_file(
                    f"kubectl --context=k3d-ess-helm get {resource} -o yaml -n {ns}", f"{output_file_prefix}.yaml"
                )

            # Get metrics of pods
            run_command_to_file(
                f"kubectl --context=k3d-ess-helm top pods -n {ns}",
                f"{destination}/{ns}/top.txt",
                # ignore failures that can happen when the test executes too fast
                check=False,
            )

            # Get events
            run_command_to_file(
                f"kubectl --context=k3d-ess-helm get events --sort-by=.metadata.creationTimestamp -n {ns}",
                f"{destination}/{ns}/events.txt",
            )

            # Get secrets (censored)
            secrets_yaml = run_command(f"kubectl --context=k3d-ess-helm get secrets -o yaml -n {ns}")
            censored_yaml = censor_secrets_yaml(secrets_yaml)
            with open(f"{destination}/{ns}/secrets.txt", "w") as f:
                f.write("----\n")
                f.write(censored_yaml)

        if system_logs:
            # Get CRDs
            run_command_to_file(
                "kubectl --context=k3d-ess-helm get crds",
                f"{destination}/crds.txt",
            )

        typer.echo(f"Logs and resources collected in {destination}")

    typer.run(_collect_logs)


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
        from dotenv import load_dotenv

        __version__ = version("ess-community-integration-tests")
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
                f"helm pull oci://ghcr.io/element-hq/ess-helm/matrix-stack:{chart_version}",
                shell=True,
                check=True,
            )

            subprocess.run(f"tar xvf matrix-stack-{chart_version}.tgz -C charts", shell=True, check=True)

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
    pytest_args = [str(HERE), str(HERE / "test_setup.py"), "--env-setup"]
    print(f"Calling pytest setup with {' '.join(pytest_args)}")
    errcode = pytest.main(pytest_args)
    subprocess.run("k3d kubeconfig merge ess-helm -ds", shell=True, check=True)

    sys.exit(errcode)
