from ..formats import escape
from .base import Node, node_type


@node_type("math")
class Math(Node):
    def to_html(self) -> str:
        return '<span class="math">\\(' + escape(self.value, "html") + "\\)</span>"

    def to_markdown(self) -> str:
        return "$" + self.value + "$"

    def to_plain(self) -> str:
        return self.value

    def to_latex(self) -> str:
        return "$" + self.value + "$"

    def to_mediawiki(self) -> str:
        return "<math>" + self.value + "</math>"

    def to_bbcode(self) -> str:
        return "[math]" + self.value + "[/math]"

    def to_org(self) -> str:
        return "\\(" + self.value + "\\)"

    def to_slack(self) -> str:
        return "`" + self.value + "`"

    def to_jira(self) -> str:
        return "{{" + self.value + "}}"

    def to_dokuwiki(self) -> str:
        return "$" + self.value + "$"

    def to_creole(self) -> str:
        return "{{{" + self.value + "}}}"

    def to_tiddlywiki(self) -> str:
        return "$$" + self.value + "$$"
