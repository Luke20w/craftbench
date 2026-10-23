"""Line-based markup languages (Markdown, Org, wikis, chat apps) all have the same document shapes, spelled
with different markers. A LineStyle lists every marker of one format; LineMarkup renders the shapes from it.
A field set to None means the format renders that shape itself, in its own method."""
from collections.abc import Callable
from dataclasses import dataclass

from ..text import prefix_lines
from .base import Renderer


@dataclass(frozen=True)
class LineStyle:
    # inline wrappers: (opening, closing) around the rendered children
    strong: tuple[str, str] | None
    emphasis: tuple[str, str]
    subscript: tuple[str, str]
    superscript: tuple[str, str]
    highlight: tuple[str, str]
    code: tuple[str, str]
    escape_code: bool                                       # whether inline code is escaped like text
    # templates: {value} is the raw value, {escaped} the value escaped like text
    kbd: str
    math: str
    link: str | None                                        # {url}, {text}
    url_escapes: str                                        # characters percent-encoded in link and image URLs
    line_break: str
    heading: Callable[[int], tuple[str, str]] | None        # level -> (before, after) the text
    code_fence: Callable[[str, str], tuple[str, str]] | None  # (language, code) -> (opening, closing) lines
    quote_prefix: str | None                                # every line of a quote gets this prefix, or
    quote_wrap: tuple[str, str] | None                      # the quote goes between these two lines
    list_nesting: str                                       # "indent": nested lists are indented;
                                                            # "stack": nested lines get the parent's marker in front
    bullet: str
    numbered: str                                           # {n}: the item's number
    list_indent: str | None                                 # continuation lines and nested lists; None: marker width
    header_cells: tuple[str, str, str] | None               # (start, between, end) of the header row
    table_cells: tuple[str, str, str] | None                # the same for the other rows
    table_rule: Callable[[int], str] | None                 # columns -> the line under the header; None: no line
    rule: str
    image: str | None                                       # {src}, {alt}, {escaped_alt}
    figure_caption: str | None                              # follows the image; {caption}


class LineMarkup(Renderer):
    style: LineStyle

    def url(self, url: str) -> str:
        for ch in self.style.url_escapes:
            url = url.replace(ch, f"%{ord(ch):02X}")
        return url

    def wrap(self, marks: tuple[str, str], node) -> str:
        return marks[0] + self.inlines(node.children) + marks[1]

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return self.wrap(self.style.strong, node)

    def emphasis(self, node) -> str:
        return self.wrap(self.style.emphasis, node)

    def subscript(self, node) -> str:
        return self.wrap(self.style.subscript, node)

    def superscript(self, node) -> str:
        return self.wrap(self.style.superscript, node)

    def highlight(self, node) -> str:
        return self.wrap(self.style.highlight, node)

    def code(self, node) -> str:
        opening, closing = self.style.code
        return opening + (self.esc(node.value) if self.style.escape_code else node.value) + closing

    def kbd(self, node) -> str:
        return self.style.kbd.format(value=node.value, escaped=self.esc(node.value))

    def math(self, node) -> str:
        return self.style.math.format(value=node.value, escaped=self.esc(node.value))

    def link(self, node) -> str:
        return self.style.link.format(url=self.url(node.url), text=self.inlines(node.children))

    def line_break(self, node) -> str:
        return self.style.line_break

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading(self, node) -> str:
        before, after = self.style.heading(node.level)
        return before + self.inlines(node.children) + after

    def code_block(self, node) -> str:
        opening, closing = self.style.code_fence(node.language, node.code)
        return opening + "\n" + node.code + "\n" + closing

    def quote(self, node) -> str:
        body = self.blocks(node.children)
        if self.style.quote_wrap:
            return self.style.quote_wrap[0] + "\n" + body + "\n" + self.style.quote_wrap[1]
        return prefix_lines(body, self.style.quote_prefix)

    def list(self, node) -> str:
        lines = []
        for number, item in enumerate(node.items, 1):
            marker = self.style.numbered.format(n=number) if node.ordered else self.style.bullet
            if self.style.list_nesting == "stack":
                lines.append(marker + " " + self.inlines(item.children))
                if item.sublist:
                    lines.append(prefix_lines(self.render(item.sublist), marker))
                continue
            indent = " " * len(marker) if self.style.list_indent is None else self.style.list_indent
            lines.append(prefix_lines(self.inlines(item.children), marker, indent))
            if item.sublist:
                lines.append(prefix_lines(self.render(item.sublist), indent))
        return "\n".join(lines)

    def table(self, node) -> str:
        def row(cells, parts):
            start, between, end = parts
            return start + between.join(self.inlines(cell) for cell in cells) + end
        lines = [row(node.header, self.style.header_cells)]
        if self.style.table_rule:
            lines.append(self.style.table_rule(len(node.header)))
        lines += [row(cells, self.style.table_cells) for cells in node.rows]
        return "\n".join(lines)

    def aligned(self, node) -> tuple[list[list[str]], list[int]]:
        """Rendered table cells, header first, and each column's width: for formats that align columns."""
        rows = [[self.inlines(cell) for cell in node.header]] + [[self.inlines(cell) for cell in cells] for cells in node.rows]
        return rows, [max(len(cells[i]) for cells in rows) for i in range(len(node.header))]

    def rule(self, node) -> str:
        return self.style.rule

    def image(self, node) -> str:
        return self.style.image.format(src=self.url(node.src), alt=node.alt, escaped_alt=self.esc(node.alt))

    def figure(self, node) -> str:
        return self.image(node) + self.style.figure_caption.format(caption=self.inlines(node.caption))
