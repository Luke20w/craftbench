from ..formats import inlines
from .base import Node, node_type


@node_type("highlight")
class Highlight(Node):
    def to_html(self) -> str:
        return "<mark>" + inlines(self.children, "html") + "</mark>"

    def to_markdown(self) -> str:
        return "==" + inlines(self.children, "markdown") + "=="

    def to_plain(self) -> str:
        return ">>" + inlines(self.children, "plain") + "<<"

    def to_latex(self) -> str:
        return "\\hl{" + inlines(self.children, "latex") + "}"

    def to_mediawiki(self) -> str:
        return "<mark>" + inlines(self.children, "mediawiki") + "</mark>"

    def to_bbcode(self) -> str:
        return "[highlight]" + inlines(self.children, "bbcode") + "[/highlight]"

    def to_org(self) -> str:
        return "@@html:<mark>@@" + inlines(self.children, "org") + "@@html:</mark>@@"

    def to_slack(self) -> str:
        return "*_" + inlines(self.children, "slack") + "_*"

    def to_jira(self) -> str:
        return "{color:#ffab00}" + inlines(self.children, "jira") + "{color}"

    def to_dokuwiki(self) -> str:
        return "<color black/yellow>" + inlines(self.children, "dokuwiki") + "</color>"

    def to_creole(self) -> str:
        return "__" + inlines(self.children, "creole") + "__"

    def to_tiddlywiki(self) -> str:
        return "@@" + inlines(self.children, "tiddlywiki") + "@@"
