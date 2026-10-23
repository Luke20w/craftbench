from .lightweight import LineMarkup


class MediaWikiRenderer(LineMarkup):
    highlight_marks = ("<mark>", "</mark>")
    kbd_template = "<kbd>{escaped}</kbd>"
    math_template = "<math>{value}</math>"
    strong_marks = ("'''", "'''")
    emphasis_marks = ("''", "''")
    code_marks = ("<code>", "</code>")
    escape_code = True
    link_template = "[{url} {text}]"
    line_break_text = "<br />"
    quote_wrap = ("<blockquote>", "</blockquote>")
    list_style = "stack"
    rule_text = "----"
    image_template = "[[File:{src}|{escaped_alt}]]"

    def esc(self, text: str) -> str:
        for ch, entity in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("[", "&#91;"), ("]", "&#93;")):
            text = text.replace(ch, entity)
        return text

    def heading_marks(self, level: int) -> tuple[str, str]:
        marks = "=" * (min(level, 5) + 1)
        return marks + " ", " " + marks

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
