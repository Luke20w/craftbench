from .base import Node, node_type


@node_type("rule")
class Rule(Node):
    def to_html(self) -> str:
        return "<hr>"

    def to_markdown(self) -> str:
        return "---"

    def to_plain(self) -> str:
        return "* * *"

    def to_latex(self) -> str:
        return "\\noindent\\rule{\\linewidth}{0.4pt}"

    def to_mediawiki(self) -> str:
        return "----"

    def to_bbcode(self) -> str:
        return "[hr]"

    def to_org(self) -> str:
        return "-----"

    def to_slack(self) -> str:
        return "----------"

    def to_jira(self) -> str:
        return "----"

    def to_dokuwiki(self) -> str:
        return "----"

    def to_creole(self) -> str:
        return "----"

    def to_tiddlywiki(self) -> str:
        return "---"
