#!/usr/bin/env python3

# Copyright 2024 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

import ruamel.yaml
import typer
import yaml as pyyaml


def find_news_fragments(root_dir):
    new_fragments = []

    for path in Path(root_dir).glob("*"):
        if path.is_file() and path.name != ".gitkeep":
            kind = path.name.split(".")[1]
            if kind != "internal":
                new_fragments.append(
                    {
                        "description": path.read_text().strip(),
                        "kind": kind,
                    }
                )
    kind_order = ["added", "changed", "deprecated", "removed", "fixed", "security"]
    # We order the list by kind and description alphabetically
    new_fragments.sort(key=lambda x: str(kind_order.index(x["kind"])) + x["description"])
    return new_fragments


def str_representer(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def towncrier_to_helm_annotation(chart_path: Path):
    yaml = ruamel.yaml.YAML(typ="rt")
    yaml.representer.add_representer(str, str_representer)
    chart_content = yaml.load(chart_path / "Chart.yaml")

    chart_content["annotations"] = chart_content.get("annotations", {})

    # We generate a list matching artfifacthub annotations format
    # https://artifacthub.io/docs/topics/annotations/helm/#example
    with open(chart_path / "Chart.yaml", "w") as overwrite_chart_yaml:
        annotation_changes = pyyaml.dump(find_news_fragments(Path().resolve() / "newsfragments"))
        chart_content["annotations"]["artifacthub.io/changes"] = annotation_changes
        yaml.dump(chart_content, overwrite_chart_yaml)


def main():
    typer.run(towncrier_to_helm_annotation)


if __name__ == "__main__":
    main()
