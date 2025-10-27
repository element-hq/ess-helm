#!/usr/bin/env python3

# Copyright 2025 Element Creations Ltd
# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import re
import sys
from typing import Annotated

import typer
from spdx_tools.spdx.model import Document
from spdx_tools.spdx.parser.tagvalue.parser import Parser

# REUSE-IgnoreStart
copyright_pattern = re.compile(r"^Copyright (?P<from>20\d{2})(-(?P<to>20\d{2}))? (?P<entity>.*)$")
# REUSE-IgnoreEnd


def run_spdx_checks(input_file: Annotated[typer.FileText, typer.Argument()]):
    parser = Parser()

    document: Document = parser.parse(input_file.read())
    failure_messages = []
    for file in document.files:
        textual_licenses = [license.render() for license in file.license_info_in_file]
        if len(textual_licenses) != 1:
            failure_messages.append(
                f'{file.name} should have exactly 1 license. It has "{", ".join(textual_licenses)}"'
            )
            continue

        if set(["AGPL-3.0-only"]) != set(textual_licenses):
            failure_messages.append(f'{file.name} has an unexpected licenses. It has "{", ".join(textual_licenses)}"')

        has_element_copyright = False
        copyrights = file.copyright_text.splitlines()
        for copyright in copyrights:
            copyright_details = copyright_pattern.match(copyright)
            if copyright_details is None:
                continue

            from_year = int(copyright_details.group("from"))
            to_year = copyright_details.group("to")
            to_year = int(to_year) if to_year else from_year

            entity = copyright_details.group("entity")
            if entity in ["New Vector Ltd", "Element Creations Ltd"]:
                has_element_copyright = True

            # REUSE-IgnoreStart
            if entity == "New Vector Ltd":
                if from_year > 2025:
                    failure_messages.append(
                        f"{file.name} has a New Vector Copyright header starting after the entity rename. "
                        f'It has "{copyright}"'
                    )
                if to_year > 2025:
                    failure_messages.append(
                        f"{file.name} has a New Vector Copyright header ending after the entity rename. "
                        f'It has "{copyright}"'
                    )

            if entity == "Element Creations Ltd":
                if from_year < 2025:
                    failure_messages.append(
                        f"{file.name} has a Element Copyright header starting before the entity rename. "
                        f'It has "{copyright}"'
                    )
                if to_year < 2025:
                    failure_messages.append(
                        f"{file.name} has a Element Copyright header ending before the entity rename. "
                        f'It has "{copyright}"'
                    )

        if not has_element_copyright:
            failure_messages.append(
                f'{file.name} doesn\'t have an Element Copyright header. It has "{file.copyright_text}"'
            )
        # REUSE-IgnoreEnd

    for failure_message in failure_messages:
        print(failure_message)
    sys.exit(0 if len(failure_messages) == 0 else 1)


def main():
    typer.run(run_spdx_checks)


if __name__ == "__main__":
    main()
