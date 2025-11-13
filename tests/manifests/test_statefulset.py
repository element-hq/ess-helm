# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from . import values_files_to_test


@pytest.mark.parametrize("values_file", values_files_to_test)
@pytest.mark.asyncio_cooperative
async def test_statefulsets_have_headless_services(templates):
    statefulsets = []
    services = []
    for template in templates:
        if template["kind"] == "StatefulSet":
            statefulsets.append(template)
        elif template["kind"] == "Service":
            services.append(template)

    services_by_name = {service["metadata"]["name"]: service for service in services}
    service_names = list(services_by_name.keys())

    for statefulset in statefulsets:
        id = statefulset["metadata"]["name"]

        assert "serviceName" in statefulset["spec"], f"{id} does not specify a Service to use"
        service_name = statefulset["spec"]["serviceName"]

        assert service_name in service_names, f"Service/{service_name} for {id} is not present in cluster"
        service = services_by_name[service_name]

        assert "clusterIP" in service["spec"], f"Service/{service_name} for {id} does not specify clusterIP"
        assert service["spec"]["clusterIP"] == "None", f"Service/{service_name} for {id} is not headless"
