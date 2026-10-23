from ..formats import inlines
from .base import Node, node_type


@node_type("paragraph")
class Paragraph(Node):
    def to_html(self) -> str:
        return "<p>" + inlines(self.children, "html") + "</p>"

    def to_markdown(self) -> str:
        return inlines(self.children, "markdown")

    def to_plain(self) -> str:
        return inlines(self.children, "plain")

    def to_latex(self) -> str:
        return inlines(self.children, "latex")

    def to_mediawiki(self) -> str:
        return inlines(self.children, "mediawiki")

    def to_bbcode(self) -> str:
        return inlines(self.children, "bbcode")

    def to_org(self) -> str:
        return inlines(self.children, "org")

    def to_slack(self) -> str:
        return inlines(self.children, "slack")

    def to_jira(self) -> str:
        return inlines(self.children, "jira")

    def to_dokuwiki(self) -> str:
        return inlines(self.children, "dokuwiki")

    def to_creole(self) -> str:
        return inlines(self.children, "creole")

    def to_tiddlywiki(self) -> str:
        return inlines(self.children, "tiddlywiki")
