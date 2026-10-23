from ..formats import inlines
from .base import Node, node_type


@node_type("table")
class Table(Node):
    def to_html(self) -> str:
        lines = ["<table>", "<tr>" + "".join("<th>" + inlines(cell, "html") + "</th>" for cell in self.header) + "</tr>"]
        for row in self.rows:
            lines.append("<tr>" + "".join("<td>" + inlines(cell, "html") + "</td>" for cell in row) + "</tr>")
        lines.append("</table>")
        return "\n".join(lines)

    def to_markdown(self) -> str:
        def row(cells):
            return "| " + " | ".join(inlines(cell, "markdown") for cell in cells) + " |"
        lines = [row(self.header), "|" + "|".join(" --- " for _ in self.header) + "|"]
        lines += [row(cells) for cells in self.rows]
        return "\n".join(lines)

    def to_plain(self) -> str:
        rows = [[inlines(cell, "plain") for cell in self.header]] + [[inlines(cell, "plain") for cell in cells] for cells in self.rows]
        widths = [max(len(cells[i]) for cells in rows) for i in range(len(self.header))]
        def line(cells):
            return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()
        lines = [line(rows[0]), "-+-".join("-" * width for width in widths)]
        lines += [line(cells) for cells in rows[1:]]
        return "\n".join(lines)

    def to_latex(self) -> str:
        columns = "|" + "|".join("l" for _ in self.header) + "|"
        lines = ["\\begin{tabular}{" + columns + "}", "\\hline", " & ".join(inlines(cell, "latex") for cell in self.header) + " \\\\", "\\hline"]
        for cells in self.rows:
            lines.append(" & ".join(inlines(cell, "latex") for cell in cells) + " \\\\")
        lines += ["\\hline", "\\end{tabular}"]
        return "\n".join(lines)

    def to_mediawiki(self) -> str:
        lines = ['{| class="wikitable"', "! " + " !! ".join(inlines(cell, "mediawiki") for cell in self.header)]
        for cells in self.rows:
            lines += ["|-", "| " + " || ".join(inlines(cell, "mediawiki") for cell in cells)]
        lines.append("|}")
        return "\n".join(lines)

    def to_bbcode(self) -> str:
        lines = ["[table]", "[tr]" + "".join("[th]" + inlines(cell, "bbcode") + "[/th]" for cell in self.header) + "[/tr]"]
        for cells in self.rows:
            lines.append("[tr]" + "".join("[td]" + inlines(cell, "bbcode") + "[/td]" for cell in cells) + "[/tr]")
        lines.append("[/table]")
        return "\n".join(lines)

    def to_org(self) -> str:
        def row(cells):
            return "| " + " | ".join(inlines(cell, "org") for cell in cells) + " |"
        lines = [row(self.header), "|" + "+".join("---" for _ in self.header) + "|"]
        lines += [row(cells) for cells in self.rows]
        return "\n".join(lines)

    def to_slack(self) -> str:
        rows = [[inlines(cell, "slack") for cell in self.header]] + [[inlines(cell, "slack") for cell in cells] for cells in self.rows]
        widths = [max(len(cells[i]) for cells in rows) for i in range(len(self.header))]
        lines = ["  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip() for cells in rows]
        return "```\n" + "\n".join(lines) + "\n```"

    def to_jira(self) -> str:
        lines = ["||" + "||".join(inlines(cell, "jira") for cell in self.header) + "||"]
        lines += ["|" + "|".join(inlines(cell, "jira") for cell in cells) + "|" for cells in self.rows]
        return "\n".join(lines)

    def to_dokuwiki(self) -> str:
        lines = ["^ " + " ^ ".join(inlines(cell, "dokuwiki") for cell in self.header) + " ^"]
        lines += ["| " + " | ".join(inlines(cell, "dokuwiki") for cell in cells) + " |" for cells in self.rows]
        return "\n".join(lines)

    def to_creole(self) -> str:
        lines = ["|=" + "|=".join(inlines(cell, "creole") for cell in self.header) + "|"]
        lines += ["|" + "|".join(inlines(cell, "creole") for cell in cells) + "|" for cells in self.rows]
        return "\n".join(lines)

    def to_tiddlywiki(self) -> str:
        lines = ["|!" + "|!".join(inlines(cell, "tiddlywiki") for cell in self.header) + "|"]
        lines += ["|" + "|".join(inlines(cell, "tiddlywiki") for cell in cells) + "|" for cells in self.rows]
        return "\n".join(lines)
