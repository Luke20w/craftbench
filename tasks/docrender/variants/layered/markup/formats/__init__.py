import importlib

from ..core.registry import REGISTRY, Registry

FORMAT_MODULES = [
    "html",
"markdown",
"plain",
"latex",
"mediawiki",
"bbcode",
"org",
"slack",
"jira",
"dokuwiki",
"creole",
"tiddlywiki",
]


def load_formats() -> Registry:
    """Import every format package so its spec and cells register themselves."""
    for name in FORMAT_MODULES:
        importlib.import_module(f"{__name__}.{name}")
    return REGISTRY
