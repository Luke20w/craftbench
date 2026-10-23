from ..formats import inlines
from .base import Node, node_type


@node_type("superscript")
class Superscript(Node):
    def to_html(self) -> str:
        return "<sup>" + inlines(self.children, "html") + "</sup>"

    def to_markdown(self) -> str:
        return "<sup>" + inlines(self.children, "markdown") + "</sup>"

    def to_plain(self) -> str:
        return "^" + inlines(self.children, "plain")

    def to_latex(self) -> str:
        return "\\textsuperscript{" + inlines(self.children, "latex") + "}"

    def to_mediawiki(self) -> str:
        return "<sup>" + inlines(self.children, "mediawiki") + "</sup>"

    def to_bbcode(self) -> str:
        return "[sup]" + inlines(self.children, "bbcode") + "[/sup]"

    def to_org(self) -> str:
        return "^{" + inlines(self.children, "org") + "}"

    def to_slack(self) -> str:
        return inlines(self.children, "slack")

    def to_jira(self) -> str:
        return "^" + inlines(self.children, "jira") + "^"

    def to_dokuwiki(self) -> str:
        return "<sup>" + inlines(self.children, "dokuwiki") + "</sup>"

    def to_creole(self) -> str:
        return "^^" + inlines(self.children, "creole") + "^^"

    def to_tiddlywiki(self) -> str:
        return "^^" + inlines(self.children, "tiddlywiki") + "^^"
