from .lightweight import LineMarkup, LineStyle


class OrgRenderer(LineMarkup):
    style = LineStyle(
        strong=("*", "*"), emphasis=("/", "/"), subscript=("_{", "}"), superscript=("^{", "}"),
        highlight=("@@html:<mark>@@", "@@html:</mark>@@"), code=("~", "~"), escape_code=False,
        kbd="={value}=", math="\\({value}\\)", link="[[{url}][{text}]]", url_escapes="", line_break="\\\\\n",
        heading=lambda level: ("*" * level + " ", ""),
        code_fence=lambda language, code: ("#+BEGIN_SRC " + language if language else "#+BEGIN_SRC", "#+END_SRC"),
        quote_prefix=None, quote_wrap=("#+BEGIN_QUOTE", "#+END_QUOTE"),
        list_nesting="indent", bullet="- ", numbered="{n}. ", list_indent=None,
        header_cells=("| ", " | ", " |"), table_cells=("| ", " | ", " |"),
        table_rule=lambda columns: "|" + "+".join("---" for _ in range(columns)) + "|",
        rule="-----", image=None, figure_caption=None,
    )

    def esc(self, text: str) -> str:
        return text.replace("[[", "[​[")

    # Shapes Org renders its own way

    def image(self, node) -> str:
        caption = "#+CAPTION: " + node.alt + "\n" if node.alt else ""
        return caption + "[[" + node.src + "]]"

    def figure(self, node) -> str:
        return "#+CAPTION: " + self.inlines(node.caption) + "\n[[" + node.src + "]]"
