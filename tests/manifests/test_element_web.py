# Copyright 2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import json

import pytest


@pytest.mark.parametrize("values_file", ["element-web-minimal-values.yaml"])
@pytest.mark.asyncio_cooperative
async def test_config_json_override(values, make_templates):
    for template in await make_templates(values):
        if template["kind"] == "ConfigMap" and "element-web" in template["metadata"]["name"]:
            config_json = json.loads(template["data"]["config.json"])
            assert config_json == {
                "bug_report_endpoint_url": "https://rageshakes.element.io/api/submit",
                "default_server_config": {"m.homeserver": {}},
                "map_style_url": "https://api.maptiler.com/maps/streets/style.json?key=fU3vlMsMn4Jb6dnEIFsx",
                "mobile_guide_app_variant": "element",
                "setting_defaults": {},
            }
            break
    else:
        raise RuntimeError("Could not find config.json")

    values["elementWeb"]["additional"] = {
        "000-comes-first": json.dumps(
            {
                "bug_report_endpoint_url": "https://other-url",
                "mobile_guide_app_variant": "element-classic",
                "some_key": {"some_subkey": "value"},
                "other_key": {"other_value": "value_second"},
            }
        ),
        "001-comes-second": json.dumps(
            {"some_key": {"some_subkey": "override"}, "again_other_key": {"other_value": "value_third"}}
        ),
    }

    for template in await make_templates(values):
        if template["kind"] == "ConfigMap" and "element-web" in template["metadata"]["name"]:
            config_json = json.loads(template["data"]["config.json"])
            assert config_json == {
                "bug_report_endpoint_url": "https://other-url",
                "default_server_config": {"m.homeserver": {}},
                "map_style_url": "https://api.maptiler.com/maps/streets/style.json?key=fU3vlMsMn4Jb6dnEIFsx",
                "mobile_guide_app_variant": "element-classic",
                "setting_defaults": {},
                "other_key": {"other_value": "value_second"},
                "some_key": {"some_subkey": "override"},
                "again_other_key": {"other_value": "value_third"},
            }
            break
    else:
        raise RuntimeError("Could not find config.json")
