from ..formats import blocks
from ..text import prefix_lines
from .base import Node, node_type


@node_type("quote")
class Quote(Node):
    def to_html(self) -> str:
        return "<blockquote>\n" + blocks(self.children, "html") + "\n</blockquote>"

    def to_markdown(self) -> str:
        return prefix_lines(blocks(self.children, "markdown"), "> ")

    def to_plain(self) -> str:
        return prefix_lines(blocks(self.children, "plain"), "| ")

    def to_latex(self) -> str:
        return "\\begin{quote}\n" + blocks(self.children, "latex") + "\n\\end{quote}"

    def to_mediawiki(self) -> str:
        return "<blockquote>\n" + blocks(self.children, "mediawiki") + "\n</blockquote>"

    def to_bbcode(self) -> str:
        return "[quote]\n" + blocks(self.children, "bbcode") + "\n[/quote]"

    def to_org(self) -> str:
        return "#+BEGIN_QUOTE\n" + blocks(self.children, "org") + "\n#+END_QUOTE"

    def to_slack(self) -> str:
        return prefix_lines(blocks(self.children, "slack"), "> ")

    def to_jira(self) -> str:
        return "{quote}\n" + blocks(self.children, "jira") + "\n{quote}"

    def to_dokuwiki(self) -> str:
        return prefix_lines(blocks(self.children, "dokuwiki"), "> ")

    def to_creole(self) -> str:
        return prefix_lines(blocks(self.children, "creole"), "> ")

    def to_tiddlywiki(self) -> str:
        return "<<<\n" + blocks(self.children, "tiddlywiki") + "\n<<<"
