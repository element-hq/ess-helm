# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import re
from hashlib import sha1

import pytest

from . import PropertyType, secret_values_files_to_test, values_files_to_test
from .utils import template_id


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_templates_have_expected_labels(release_name, templates):
    expected_labels = [
        "helm.sh/chart",
        "app.kubernetes.io/managed-by",
        "app.kubernetes.io/part-of",
        "app.kubernetes.io/name",
        "app.kubernetes.io/component",
        "app.kubernetes.io/instance",
        "app.kubernetes.io/version",
    ]

    for template in templates:
        id = template_id(template)
        labels = template["metadata"]["labels"]

        for expected_label in expected_labels:
            assert expected_label in labels, f"{expected_label} label not present in {id}"
            assert labels[expected_label] is not None, (
                f"{expected_label} label is null in {id} and so won't be present in cluster"
            )

        assert labels["helm.sh/chart"].startswith("matrix-stack-")
        assert labels["app.kubernetes.io/managed-by"] == "Helm"
        assert labels["app.kubernetes.io/part-of"] == "matrix-stack"

        # The instance label is <release name>-<name label>.
        assert labels["app.kubernetes.io/instance"].startswith(f"{release_name}-"), (
            f"The app.kubernetes.io/instance label for {id}"
            f"does not start with the expected chart release name of '{release_name}'. "
        )
        f"The label value is {labels['app.kubernetes.io/instance']}"

        assert (
            labels["app.kubernetes.io/instance"].replace(f"{release_name}-", "") == labels["app.kubernetes.io/name"]
        ), (
            f"The app.kubernetes.io/name label for {id}"
            "is not a concatenation of the expected chart release name of '{release_name}' and the instance label. "
            f"The label value is {labels['app.kubernetes.io/instance']} vs {labels['app.kubernetes.io/name']}"
        )


@pytest.mark.parametrize("values_file", secret_values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_templates_have_postgres_hash_label(release_name, templates, values, template_to_deployable_details):
    for template in templates:
        if template["kind"] in ["Deployment", "StatefulSet", "Job"]:
            id = template_id(template)
            labels = template["spec"]["template"]["metadata"]["labels"]
            deployable_details = template_to_deployable_details(template)
            if not deployable_details.has_db:
                continue

            assert "k8s.element.io/postgres-password-hash" in labels, f"{id} does not have postgres password hash label"
            # We currently assume that Postgres is for top-level components only and so there is a single segment
            # write (or read) path
            assert len(deployable_details.values_file_path.write_path) == 1
            helm_key = deployable_details.values_file_path.read_path[0]
            values_fragment = deployable_details.get_helm_values(values, PropertyType.Postgres)
            if values_fragment.get("password", {}).get("value", None):
                expected = values_fragment["password"]["value"]
            elif values_fragment.get("password", {}).get("secret", None):
                secret_name = values_fragment["password"]["secret"]
                expected = f"{secret_name}-{values_fragment['password']['secretKey']}"
            elif values["postgres"].get("essPasswords", {}).get(helm_key, {}).get("value", None):
                expected = values["postgres"]["essPasswords"][helm_key]["value"]
            elif values["postgres"].get("essPasswords", {}).get(helm_key, {}).get("secret", None):
                secret_name = values["postgres"]["essPasswords"][helm_key]["secret"]
                expected = f"{secret_name}-{values['postgres']['essPasswords'][helm_key]['secretKey']}"
            else:
                expected = f"{release_name}-generated"
            expected = expected.replace("{{ $.Release.Name }}", release_name)
            assert labels["k8s.element.io/postgres-password-hash"] == sha1(expected.encode()).hexdigest(), (
                f"{id} has incorrect postgres password hash, expect {expected} hashed as sha1"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_pod_spec_labels_are_consistent_with_parent_labels(templates):
    for template in templates:
        if template["kind"] not in ["Deployment", "Job", "StatefulSet"]:
            continue

        parent_labels = template["metadata"]["labels"]
        pod_labels = template["spec"]["template"]["metadata"]["labels"]

        # Explicitly omitted from Pod labels so that they don't restart blindly on chart upgrade
        del parent_labels["helm.sh/chart"]

        assert parent_labels == pod_labels, (
            f"{template_id(template)} has differing labels between itself and the Pods it would create. "
            f"{parent_labels=} vs {pod_labels=}"
        )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_our_labels_are_named_consistently(templates):
    acceptable_matches = [
        "k8s.element.io/as-registration-[0-9]+-hash",
        "k8s.element.io/([a-z0-9-]+)-(config|secret)-hash",
        "k8s.element.io/postgres-password-hash",
        "k8s.element.io/synapse-instance",
        "k8s.element.io/target-(instance|name)",
    ]
    for template in templates:
        labels = template["metadata"]["labels"]
        our_labels = [key for key in labels if "k8s.element.io" in key]
        for our_label in our_labels:
            has_match = any(
                [re.match(f"^{acceptable_match}$", our_label) is not None for acceptable_match in acceptable_matches]
            )
            assert has_match, (
                f"{template_id(template)} has label {our_label} that does not match one of {acceptable_matches=}"
            )
