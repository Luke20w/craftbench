from ..formats import inlines
from .base import Node, node_type


@node_type("heading")
class Heading(Node):
    def to_html(self) -> str:
        level = min(self.level, 6)
        return f"<h{level}>" + inlines(self.children, "html") + f"</h{level}>"

    def to_markdown(self) -> str:
        return "#" * min(self.level, 6) + " " + inlines(self.children, "markdown")

    def to_plain(self) -> str:
        text = inlines(self.children, "plain")
        if self.level == 1:
            return text + "\n" + "=" * len(text)
        if self.level == 2:
            return text + "\n" + "-" * len(text)
        return text

    def to_latex(self) -> str:
        command = {1: "section", 2: "subsection"}.get(self.level, "subsubsection")
        return "\\" + command + "{" + inlines(self.children, "latex") + "}"

    def to_mediawiki(self) -> str:
        marks = "=" * (min(self.level, 5) + 1)
        return marks + " " + inlines(self.children, "mediawiki") + " " + marks

    def to_bbcode(self) -> str:
        size = {1: 200, 2: 150}.get(self.level, 120)
        return f"[size={size}%][b]" + inlines(self.children, "bbcode") + "[/b][/size]"

    def to_org(self) -> str:
        return "*" * self.level + " " + inlines(self.children, "org")

    def to_slack(self) -> str:
        return "*" + inlines(self.children, "slack") + "*"

    def to_jira(self) -> str:
        return f"h{min(self.level, 6)}. " + inlines(self.children, "jira")

    def to_dokuwiki(self) -> str:
        marks = "=" * (7 - min(self.level, 5))
        return marks + " " + inlines(self.children, "dokuwiki") + " " + marks

    def to_creole(self) -> str:
        return "=" * min(self.level, 6) + " " + inlines(self.children, "creole")

    def to_tiddlywiki(self) -> str:
        return "!" * min(self.level, 6) + " " + inlines(self.children, "tiddlywiki")
