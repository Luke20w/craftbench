from .lightweight import LineMarkup, LineStyle


class DokuWikiRenderer(LineMarkup):
    style = LineStyle(
        strong=("**", "**"), emphasis=("//", "//"), subscript=("<sub>", "</sub>"), superscript=("<sup>", "</sup>"),
        highlight=("<color black/yellow>", "</color>"), code=("''", "''"), escape_code=False,
        kbd="<key>{value}</key>", math="${value}$", link="[[{url}|{text}]]", url_escapes="", line_break="\\\\ ",
        heading=lambda level: ("=" * (7 - min(level, 5)) + " ", " " + "=" * (7 - min(level, 5))),
        code_fence=lambda language, code: ("<code " + language + ">" if language else "<code>", "</code>"),
        quote_prefix="> ", quote_wrap=None,
        list_nesting="indent", bullet="  * ", numbered="  - ", list_indent="  ",
        header_cells=("^ ", " ^ ", " ^"), table_cells=("| ", " | ", " |"),
        table_rule=None,
        rule="----", image="{{{{{src}|{alt}}}}}", figure_caption=None,
    )

    def esc(self, text: str) -> str:
        if any(ch in text for ch in "*/[]_'^|<>{}"):
            return "%%" + text + "%%"
        return text

    # Shapes DokuWiki renders its own way

    def figure(self, node) -> str:
        return "{{" + node.src + "|" + self.inlines(node.caption) + "}}"
