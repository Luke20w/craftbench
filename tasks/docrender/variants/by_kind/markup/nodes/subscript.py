from ..formats import inlines
from .base import Node, node_type


@node_type("subscript")
class Subscript(Node):
    def to_html(self) -> str:
        return "<sub>" + inlines(self.children, "html") + "</sub>"

    def to_markdown(self) -> str:
        return "<sub>" + inlines(self.children, "markdown") + "</sub>"

    def to_plain(self) -> str:
        return "_" + inlines(self.children, "plain")

    def to_latex(self) -> str:
        return "\\textsubscript{" + inlines(self.children, "latex") + "}"

    def to_mediawiki(self) -> str:
        return "<sub>" + inlines(self.children, "mediawiki") + "</sub>"

    def to_bbcode(self) -> str:
        return "[sub]" + inlines(self.children, "bbcode") + "[/sub]"

    def to_org(self) -> str:
        return "_{" + inlines(self.children, "org") + "}"

    def to_slack(self) -> str:
        return inlines(self.children, "slack")

    def to_jira(self) -> str:
        return "~" + inlines(self.children, "jira") + "~"

    def to_dokuwiki(self) -> str:
        return "<sub>" + inlines(self.children, "dokuwiki") + "</sub>"

    def to_creole(self) -> str:
        return ",," + inlines(self.children, "creole") + ",,"

    def to_tiddlywiki(self) -> str:
        return ",," + inlines(self.children, "tiddlywiki") + ",,"
