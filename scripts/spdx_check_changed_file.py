#!/usr/bin/env python3

# Copyright 2025 Element Creations Ltd
# Copyright 2025 New Vector Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import re
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from spdx_tools.spdx.model import Document
from spdx_tools.spdx.parser.tagvalue.parser import Parser

# REUSE-IgnoreStart
copyright_pattern = re.compile(r"^Copyright (?P<from>20\d{2})(-(?P<to>20\d{2}))? (?P<entity>.*)$")
# REUSE-IgnoreEnd


def do_changed_files_have_correct_copyright_header(
    spdx_file: Annotated[typer.FileText, typer.Argument()], changed_filenames: list[str]
):
    assert len(changed_filenames) > 0

    parser = Parser()

    document: Document = parser.parse(spdx_file.read())
    spdx_details_by_filename = {}
    for file in document.files:
        spdx_details_by_filename[file.name.removeprefix("./")] = file

    current_year = date.today().year
    failure_messages = []
    for changed_filename in changed_filenames:
        # REUSE.toml isn't included in the SPDX
        if changed_filename == "REUSE.toml":
            continue

        if not Path(changed_filename).exists():
            print(f"{changed_filename} is being skipped as it doesn't exist")
            continue

        assert changed_filename in spdx_details_by_filename
        file = spdx_details_by_filename[changed_filename]

        has_new_element_copyright = False
        copyrights = file.copyright_text.splitlines()
        for copyright in copyrights:
            copyright_details = copyright_pattern.match(copyright)
            if copyright_details is None:
                continue

            from_year = int(copyright_details.group("from"))
            to_year = copyright_details.group("to")
            to_year = int(to_year) if to_year else from_year

            entity = copyright_details.group("entity")
            if entity != "Element Creations Ltd":
                continue

            # REUSE-IgnoreStart
            has_new_element_copyright = True
            if to_year < current_year:
                failure_messages.append(
                    f"{changed_filename}'s Element Creations Ltd Copyright header doesn't extend to "
                    f'{current_year}, only {to_year}. It has "{copyright}"'
                )

        if not has_new_element_copyright:
            failure_messages.append(
                f"{changed_filename} doesn't have a 'Element Creations Ltd' Copyright header. "
                f'It has "{file.copyright_text}"'
            )
        # REUSE-IgnoreEnd

    for failure_message in failure_messages:
        print(failure_message, file=sys.stderr)
    sys.exit(0 if len(failure_messages) == 0 else 1)


def main():
    typer.run(do_changed_files_have_correct_copyright_header)


if __name__ == "__main__":
    main()
