"""Sphinx configuration for the Paeonia documentation."""

project = "Paeonia"
author = "Vytautas Jancauskas"
copyright = "2026, Vytautas Jancauskas"
release = "0.0.1"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "show-inheritance": True,
}
autodoc_typehints = "description"
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
html_theme_options = {
    "description": "Computer-assisted composition with spelled pitches",
    "github_button": True,
    "github_repo": "paeonia",
    "github_user": "orbitfold",
}
html_title = "Paeonia documentation"
