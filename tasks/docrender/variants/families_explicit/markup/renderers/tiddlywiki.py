from .lightweight import LineMarkup, LineStyle


class TiddlyWikiRenderer(LineMarkup):
    style = LineStyle(
        strong=("''", "''"), emphasis=("//", "//"), subscript=(",,", ",,"), superscript=("^^", "^^"),
        highlight=("@@", "@@"), code=("`", "`"), escape_code=False,
        kbd="<kbd>{value}</kbd>", math="$${value}$$", link="[[{text}|{url}]]", url_escapes="", line_break="<br>",
        heading=lambda level: ("!" * min(level, 6) + " ", ""),
        code_fence=lambda language, code: ("```" + language, "```"),
        quote_prefix=None, quote_wrap=("<<<", "<<<"),
        list_nesting="stack", bullet="*", numbered="#", list_indent=None,
        header_cells=("|!", "|!", "|"), table_cells=("|", "|", "|"),
        table_rule=None,
        rule="---", image=None, figure_caption="\n//{caption}//",
    )

    def esc(self, text: str) -> str:
        if any(ch in text for ch in "'/`[]{}<>^~_$|"):
            return '"""' + text + '"""'
        return text

    # Shapes TiddlyWiki renders its own way

    def image(self, node) -> str:
        return "[img[" + node.alt + "|" + node.src + "]]" if node.alt else "[img[" + node.src + "]]"
