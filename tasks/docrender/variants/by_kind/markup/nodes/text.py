from ..formats import escape
from .base import Node, node_type


@node_type("text")
class Text(Node):
    def to_html(self) -> str:
        return escape(self.value, "html")

    def to_markdown(self) -> str:
        return escape(self.value, "markdown")

    def to_plain(self) -> str:
        return escape(self.value, "plain")

    def to_latex(self) -> str:
        return escape(self.value, "latex")

    def to_mediawiki(self) -> str:
        return escape(self.value, "mediawiki")

    def to_bbcode(self) -> str:
        return escape(self.value, "bbcode")

    def to_org(self) -> str:
        return escape(self.value, "org")

    def to_slack(self) -> str:
        return escape(self.value, "slack")

    def to_jira(self) -> str:
        return escape(self.value, "jira")

    def to_dokuwiki(self) -> str:
        return escape(self.value, "dokuwiki")

    def to_creole(self) -> str:
        return escape(self.value, "creole")

    def to_tiddlywiki(self) -> str:
        return escape(self.value, "tiddlywiki")
