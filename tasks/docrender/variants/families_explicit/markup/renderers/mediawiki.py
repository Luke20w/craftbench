from .lightweight import LineMarkup, LineStyle


class MediaWikiRenderer(LineMarkup):
    style = LineStyle(
        strong=("'''", "'''"), emphasis=("''", "''"), subscript=("<sub>", "</sub>"), superscript=("<sup>", "</sup>"),
        highlight=("<mark>", "</mark>"), code=("<code>", "</code>"), escape_code=True,
        kbd="<kbd>{escaped}</kbd>", math="<math>{value}</math>", link="[{url} {text}]", url_escapes="",
        line_break="<br />",
        heading=lambda level: ("=" * (min(level, 5) + 1) + " ", " " + "=" * (min(level, 5) + 1)),
        code_fence=None,
        quote_prefix=None, quote_wrap=("<blockquote>", "</blockquote>"),
        list_nesting="stack", bullet="*", numbered="#", list_indent=None,
        header_cells=None, table_cells=None,
        table_rule=None,
        rule="----", image="[[File:{src}|{escaped_alt}]]", figure_caption=None,
    )

    def esc(self, text: str) -> str:
        for ch, entity in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("[", "&#91;"), ("]", "&#93;")):
            text = text.replace(ch, entity)
        return text

    # Shapes MediaWiki renders its own way

    def code_block(self, node) -> str:
        if node.language:
            return '<syntaxhighlight lang="' + node.language + '">\n' + node.code + "\n</syntaxhighlight>"
        return "<pre>\n" + self.esc(node.code) + "\n</pre>"

    def table(self, node) -> str:
        lines = ['{| class="wikitable"', "! " + " !! ".join(self.inlines(cell) for cell in node.header)]
        for cells in node.rows:
            lines += ["|-", "| " + " || ".join(self.inlines(cell) for cell in cells)]
        lines.append("|}")
        return "\n".join(lines)

    def figure(self, node) -> str:
        return "[[File:" + node.src + "|thumb|" + self.inlines(node.caption) + "]]"
