from ..formats import escape
from .base import Node, node_type


@node_type("code")
class Code(Node):
    def to_html(self) -> str:
        return "<code>" + escape(self.value, "html") + "</code>"

    def to_markdown(self) -> str:
        if "`" in self.value:
            return "`` " + self.value + " ``"
        return "`" + self.value + "`"

    def to_plain(self) -> str:
        return self.value

    def to_latex(self) -> str:
        return "\\texttt{" + escape(self.value, "latex") + "}"

    def to_mediawiki(self) -> str:
        return "<code>" + escape(self.value, "mediawiki") + "</code>"

    def to_bbcode(self) -> str:
        return "[icode]" + escape(self.value, "bbcode") + "[/icode]"

    def to_org(self) -> str:
        return "~" + self.value + "~"

    def to_slack(self) -> str:
        return "`" + self.value + "`"

    def to_jira(self) -> str:
        return "{{" + self.value + "}}"

    def to_dokuwiki(self) -> str:
        return "''" + self.value + "''"

    def to_creole(self) -> str:
        return "{{{" + self.value + "}}}"

    def to_tiddlywiki(self) -> str:
        return "`" + self.value + "`"
