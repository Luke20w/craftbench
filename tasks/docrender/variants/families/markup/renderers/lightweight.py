"""Line-based markup languages (Markdown, Org, wikis, chat apps) all have the same document shapes, spelled
with different markers. LineMarkup renders those shapes; each format sets its markers and overrides only the
shapes it does differently. The defaults are Markdown's."""
from ..text import prefix_lines
from .base import Renderer


class LineMarkup(Renderer):
    strong_marks = ("**", "**")
    emphasis_marks = ("*", "*")
    code_marks = ("`", "`")
    subscript_marks = ("<sub>", "</sub>")
    superscript_marks = ("<sup>", "</sup>")
    highlight_marks = ("==", "==")
    kbd_template = "<kbd>{value}</kbd>"     # {value}: the raw value, {escaped}: the value escaped like text
    math_template = "${value}$"
    escape_code = False                 # whether inline code is escaped like text
    link_template = "[{text}]({url})"
    line_break_text = "\n"
    quote_prefix = "> "                 # every line of a quote gets this prefix...
    quote_wrap = None                   # ...unless the format wraps quotes in (opening, closing) lines
    list_style = "indent"               # "indent": nested lists are indented; "stack": nested markers repeat the parent's
    bullet = "- "
    numbered = "{n}. "
    list_indent = None                  # indent of continuation lines and nested lists; None: the marker's width
    table_cells = ("| ", " | ", " |")   # (start, between, end) of a table row
    header_cells = None                 # the same for the header row; None: like other rows
    rule_text = "---"
    image_template = "![{escaped_alt}]({src})"
    figure_caption = "\n\n*{caption}*"     # follows the image

    def url(self, url: str) -> str:
        return url

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return self.wrap(self.strong_marks, node)

    def emphasis(self, node) -> str:
        return self.wrap(self.emphasis_marks, node)

    def wrap(self, marks: tuple[str, str], node) -> str:
        return marks[0] + self.inlines(node.children) + marks[1]

    def subscript(self, node) -> str:
        return self.wrap(self.subscript_marks, node)

    def superscript(self, node) -> str:
        return self.wrap(self.superscript_marks, node)

    def highlight(self, node) -> str:
        return self.wrap(self.highlight_marks, node)

    def kbd(self, node) -> str:
        return self.kbd_template.format(value=node.value, escaped=self.esc(node.value))

    def math(self, node) -> str:
        return self.math_template.format(value=node.value, escaped=self.esc(node.value))

    def code(self, node) -> str:
        opening, closing = self.code_marks
        return opening + (self.esc(node.value) if self.escape_code else node.value) + closing

    def link(self, node) -> str:
        return self.link_template.format(url=self.url(node.url), text=self.inlines(node.children))

    def line_break(self, node) -> str:
        return self.line_break_text

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading_marks(self, level: int) -> tuple[str, str]:
        return "#" * min(level, 6) + " ", ""

    def heading(self, node) -> str:
        before, after = self.heading_marks(node.level)
        return before + self.inlines(node.children) + after

    def code_fence(self, language: str, code: str) -> tuple[str, str]:
        return "```" + language, "```"

    def code_block(self, node) -> str:
        opening, closing = self.code_fence(node.language, node.code)
        return opening + "\n" + node.code + "\n" + closing

    def quote(self, node) -> str:
        body = self.blocks(node.children)
        if self.quote_wrap:
            return self.quote_wrap[0] + "\n" + body + "\n" + self.quote_wrap[1]
        return prefix_lines(body, self.quote_prefix)

    def list(self, node) -> str:
        lines = []
        if self.list_style == "stack":
            marker = "#" if node.ordered else "*"
            for item in node.items:
                lines.append(marker + " " + self.inlines(item.children))
                if item.sublist:
                    lines.append(prefix_lines(self.render(item.sublist), marker))
            return "\n".join(lines)
        for number, item in enumerate(node.items, 1):
            marker = self.numbered.format(n=number) if node.ordered else self.bullet
            indent = " " * len(marker) if self.list_indent is None else self.list_indent
            lines.append(prefix_lines(self.inlines(item.children), marker, indent))
            if item.sublist:
                lines.append(prefix_lines(self.render(item.sublist), indent))
        return "\n".join(lines)

    def table_rule(self, columns: int) -> str | None:
        """The line between the header and the other rows, if the format has one."""
        return "|" + "|".join(" --- " for _ in range(columns)) + "|"

    def table(self, node) -> str:
        def row(cells, parts):
            start, between, end = parts
            return start + between.join(self.inlines(cell) for cell in cells) + end
        lines = [row(node.header, self.header_cells or self.table_cells)]
        rule = self.table_rule(len(node.header))
        if rule:
            lines.append(rule)
        lines += [row(cells, self.table_cells) for cells in node.rows]
        return "\n".join(lines)

    def aligned(self, node) -> tuple[list[list[str]], list[int]]:
        """Rendered table cells, header first, and each column's width: for formats that align columns."""
        rows = [[self.inlines(cell) for cell in node.header]] + [[self.inlines(cell) for cell in cells] for cells in node.rows]
        return rows, [max(len(cells[i]) for cells in rows) for i in range(len(node.header))]

    def rule(self, node) -> str:
        return self.rule_text

    def image(self, node) -> str:
        return self.image_template.format(src=self.url(node.src), alt=node.alt, escaped_alt=self.esc(node.alt))

    def figure(self, node) -> str:
        return self.image(node) + self.figure_caption.format(caption=self.inlines(node.caption))
