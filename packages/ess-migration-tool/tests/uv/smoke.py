"""Check that basic features work.

Catch cases where e.g. files are missing so the import doesn't work. It is
recommended to check that e.g. assets are included."""

import sys
from unittest.mock import patch

from ess_migration_tool.__main__ import main

# Mock sys.argv to simulate CLI arguments
test_args = ["migration", "--help"]

# Run the main function with mocked sys.argv
with patch.object(sys, "argv", test_args):
    exit_code = main()
