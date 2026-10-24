#!/usr/bin/env python3
"""Run the jev-workflow CLI from this skill directory without installing a package.

Resolves the bundled jev_workflow package relative to this file only.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jev_workflow.cli import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
