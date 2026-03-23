"""Sphinx configuration for Plywatch docs."""

from __future__ import annotations

import os
from datetime import datetime

project = "plywatch"
author = "massivadatascope"
copyright = f"{datetime.now().year}, {author}"
release = os.getenv("READTHEDOCS_VERSION", "latest")

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_static_path = ["_static"]
html_title = "plywatch docs"

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
