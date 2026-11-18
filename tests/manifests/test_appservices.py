# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import random
import re
import string

import pytest

from manifests.utils import iterate_deployables_parts, iterate_pod_template

from . import DeployableDetails, PropertyType, values_files_to_test


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_appservices_set_consistent_labels_on_self_and_synapse(templates):
    seen_synapse = False
    seen_appservice_hashes = {}
    seen_appservice_hashes_on_synapse = {}
    for pod_template_details in iterate_pod_template(templates):
        deployable_details = pod_template_details.deployable_details()
        if not deployable_details.is_appservice and not deployable_details.is_synapse_process:
            continue

        if deployable_details.is_appservice:
            controller_labels = pod_template_details.manifest["metadata"]["labels"]
            assert "k8s.element.io/as-registration-self-hash" in controller_labels, (
                f"{pod_template_details.manifest_id} did not have its own registration hash on the parent controller"
            )

            pod_labels = pod_template_details.pod_template["metadata"]["labels"]
            assert "k8s.element.io/as-registration-self-hash" in pod_labels, (
                f"{pod_template_details.manifest_id} did not have its own registration hash on the Pod"
            )

            # We don't need to assert the controller label matches the pod label
            # as test_pod_spec_labels_are_consistent_with_parent_labels does this
            seen_appservice_hashes[deployable_details.name] = controller_labels[
                "k8s.element.io/as-registration-self-hash"
            ]
        else:
            controller_labels = pod_template_details.manifest["metadata"]["labels"]
            appservice_hashes_on_synapse = {
                key: value
                for key, value in controller_labels.items()
                if re.match(r"^k8s.element.io/as-registration-[a-z-]+-hash$", key)
            }
            if not seen_synapse:
                seen_synapse = True
                seen_appservice_hashes_on_synapse = appservice_hashes_on_synapse
            else:
                assert seen_appservice_hashes_on_synapse == appservice_hashes_on_synapse, (
                    "Synapse has inconsistent Appservice hashes between Pods"
                )

    # As not all values files with appservices will also deploy Synapse
    if seen_synapse:
        assert len(seen_appservice_hashes) == len(seen_appservice_hashes_on_synapse), (
            "There are differing numbers of AppServices vs labels seen on Synapse ("
            f"Seen AppServices={seen_appservice_hashes.keys()} vs "
            f"AppService labels on Synapse={seen_appservice_hashes_on_synapse.keys()})"
        )
        for appservice, hash in seen_appservice_hashes.items():
            synapse_appservice_label = f"k8s.element.io/as-registration-{appservice}-hash"
            assert synapse_appservice_label in seen_appservice_hashes_on_synapse, (
                f"{appservice} didn't have a registration hash on Synapse"
            )
            assert hash == seen_appservice_hashes_on_synapse[synapse_appservice_label], (
                f"{appservice} had an inconsistent registration hash vs on Synapse"
            )


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_appservices_hash_changes_when_registration_changes(values, make_templates):
    original_hashes = {}
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        deployable_details = pod_template_details.deployable_details()
        if not deployable_details.is_appservice:
            continue

        controller_labels = pod_template_details.manifest["metadata"]["labels"]
        original_hashes[deployable_details.name] = controller_labels["k8s.element.io/as-registration-self-hash"]

    def set_registration(deployable_details: DeployableDetails):
        # We can't sensibly test the built-in template changing or the contents of an external Secret
        # So always set an inline value
        deployable_details.set_helm_values(
            values,
            PropertyType.AppServiceRegistration,
            {"value": "".join(random.choices(string.ascii_lowercase, k=20))},
        )

    iterate_deployables_parts(set_registration, lambda deployable_details: deployable_details.is_appservice)
    for pod_template_details in iterate_pod_template(await make_templates(values)):
        deployable_details = pod_template_details.deployable_details()
        if not deployable_details.is_appservice:
            continue

        controller_labels = pod_template_details.manifest["metadata"]["labels"]
        assert deployable_details.name in original_hashes, f"AppService {deployable_details.name} has suddenly appeared"
        assert (
            original_hashes[deployable_details.name] != controller_labels["k8s.element.io/as-registration-self-hash"]
        ), f"AppService {deployable_details.name} hasn't had its registration hash changed"
