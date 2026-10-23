from .base import Node, node_type


@node_type("line_break")
class LineBreak(Node):
    def to_html(self) -> str:
        return "<br>"

    def to_markdown(self) -> str:
        return "\\\n"

    def to_plain(self) -> str:
        return "\n"

    def to_latex(self) -> str:
        return "\\\\\n"

    def to_mediawiki(self) -> str:
        return "<br />"

    def to_bbcode(self) -> str:
        return "\n"

    def to_org(self) -> str:
        return "\\\\\n"

    def to_slack(self) -> str:
        return "\n"

    def to_jira(self) -> str:
        return "\n"

    def to_dokuwiki(self) -> str:
        return "\\\\ "

    def to_creole(self) -> str:
        return "\\\\"

    def to_tiddlywiki(self) -> str:
        return "<br>"
