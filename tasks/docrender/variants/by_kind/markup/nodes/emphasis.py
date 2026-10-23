from ..formats import inlines
from .base import Node, node_type


@node_type("emphasis")
class Emphasis(Node):
    def to_html(self) -> str:
        return "<em>" + inlines(self.children, "html") + "</em>"

    def to_markdown(self) -> str:
        return "*" + inlines(self.children, "markdown") + "*"

    def to_plain(self) -> str:
        return "_" + inlines(self.children, "plain") + "_"

    def to_latex(self) -> str:
        return "\\emph{" + inlines(self.children, "latex") + "}"

    def to_mediawiki(self) -> str:
        return "''" + inlines(self.children, "mediawiki") + "''"

    def to_bbcode(self) -> str:
        return "[i]" + inlines(self.children, "bbcode") + "[/i]"

    def to_org(self) -> str:
        return "/" + inlines(self.children, "org") + "/"

    def to_slack(self) -> str:
        return "_" + inlines(self.children, "slack") + "_"

    def to_jira(self) -> str:
        return "_" + inlines(self.children, "jira") + "_"

    def to_dokuwiki(self) -> str:
        return "//" + inlines(self.children, "dokuwiki") + "//"

    def to_creole(self) -> str:
        return "//" + inlines(self.children, "creole") + "//"

    def to_tiddlywiki(self) -> str:
        return "//" + inlines(self.children, "tiddlywiki") + "//"
