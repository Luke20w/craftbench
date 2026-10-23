from ..formats import escape
from .base import Node, node_type


@node_type("kbd")
class Kbd(Node):
    def to_html(self) -> str:
        return "<kbd>" + escape(self.value, "html") + "</kbd>"

    def to_markdown(self) -> str:
        return "<kbd>" + self.value + "</kbd>"

    def to_plain(self) -> str:
        return "[" + self.value + "]"

    def to_latex(self) -> str:
        return "\\fbox{\\texttt{" + escape(self.value, "latex") + "}}"

    def to_mediawiki(self) -> str:
        return "<kbd>" + escape(self.value, "mediawiki") + "</kbd>"

    def to_bbcode(self) -> str:
        return "[kbd]" + self.value + "[/kbd]"

    def to_org(self) -> str:
        return "=" + self.value + "="

    def to_slack(self) -> str:
        return "`" + self.value + "`"

    def to_jira(self) -> str:
        return "{{" + self.value + "}}"

    def to_dokuwiki(self) -> str:
        return "<key>" + self.value + "</key>"

    def to_creole(self) -> str:
        return "{{{" + self.value + "}}}"

    def to_tiddlywiki(self) -> str:
        return "<kbd>" + self.value + "</kbd>"
