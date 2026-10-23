from ..formats import inlines
from ..text import prefix_lines
from .base import Node, node_type


@node_type("list")
class List(Node):
    def to_html(self) -> str:
        tag = "ol" if self.ordered else "ul"
        items = []
        for item in self.items:
            body = inlines(item.children, "html")
            if item.sublist:
                body += "\n" + item.sublist.render("html")
            items.append("<li>" + body + "</li>")
        return f"<{tag}>\n" + "\n".join(items) + f"\n</{tag}>"

    def to_markdown(self) -> str:
        lines = []
        for number, item in enumerate(self.items, 1):
            marker = f"{number}. " if self.ordered else "- "
            lines.append(prefix_lines(inlines(item.children, "markdown"), marker, " " * len(marker)))
            if item.sublist:
                lines.append(prefix_lines(item.sublist.render("markdown"), " " * len(marker)))
        return "\n".join(lines)

    def to_plain(self) -> str:
        lines = []
        for number, item in enumerate(self.items, 1):
            marker = f"{number}) " if self.ordered else "* "
            lines.append(prefix_lines(inlines(item.children, "plain"), marker, " " * len(marker)))
            if item.sublist:
                lines.append(prefix_lines(item.sublist.render("plain"), " " * len(marker)))
        return "\n".join(lines)

    def to_latex(self) -> str:
        env = "enumerate" if self.ordered else "itemize"
        lines = ["\\begin{" + env + "}"]
        for item in self.items:
            lines.append(prefix_lines(inlines(item.children, "latex"), "  \\item ", "  "))
            if item.sublist:
                lines.append(prefix_lines(item.sublist.render("latex"), "  "))
        lines.append("\\end{" + env + "}")
        return "\n".join(lines)

    def to_mediawiki(self) -> str:
        marker = "#" if self.ordered else "*"
        lines = []
        for item in self.items:
            lines.append(marker + " " + inlines(item.children, "mediawiki"))
            if item.sublist:
                lines.append(prefix_lines(item.sublist.render("mediawiki"), marker))
        return "\n".join(lines)

    def to_bbcode(self) -> str:
        lines = ["[list=1]" if self.ordered else "[list]"]
        for item in self.items:
            lines.append("[*]" + inlines(item.children, "bbcode"))
            if item.sublist:
                lines.append(item.sublist.render("bbcode"))
        lines.append("[/list]")
        return "\n".join(lines)

    def to_org(self) -> str:
        lines = []
        for number, item in enumerate(self.items, 1):
            marker = f"{number}. " if self.ordered else "- "
            lines.append(prefix_lines(inlines(item.children, "org"), marker, " " * len(marker)))
            if item.sublist:
                lines.append(prefix_lines(item.sublist.render("org"), " " * len(marker)))
        return "\n".join(lines)

    def to_slack(self) -> str:
        lines = []
        for number, item in enumerate(self.items, 1):
            marker = f"{number}. " if self.ordered else "• "
            lines.append(prefix_lines(inlines(item.children, "slack"), marker, "    "))
            if item.sublist:
                lines.append(prefix_lines(item.sublist.render("slack"), "    "))
        return "\n".join(lines)

    def to_jira(self) -> str:
        marker = "#" if self.ordered else "*"
        lines = []
        for item in self.items:
            lines.append(marker + " " + inlines(item.children, "jira"))
            if item.sublist:
                lines.append(prefix_lines(item.sublist.render("jira"), marker))
        return "\n".join(lines)

    def to_dokuwiki(self) -> str:
        marker = "  - " if self.ordered else "  * "
        lines = []
        for item in self.items:
            lines.append(marker + inlines(item.children, "dokuwiki"))
            if item.sublist:
                lines.append(prefix_lines(item.sublist.render("dokuwiki"), "  "))
        return "\n".join(lines)

    def to_creole(self) -> str:
        marker = "#" if self.ordered else "*"
        lines = []
        for item in self.items:
            lines.append(marker + " " + inlines(item.children, "creole"))
            if item.sublist:
                lines.append(prefix_lines(item.sublist.render("creole"), marker))
        return "\n".join(lines)

    def to_tiddlywiki(self) -> str:
        marker = "#" if self.ordered else "*"
        lines = []
        for item in self.items:
            lines.append(marker + " " + inlines(item.children, "tiddlywiki"))
            if item.sublist:
                lines.append(prefix_lines(item.sublist.render("tiddlywiki"), marker))
        return "\n".join(lines)
