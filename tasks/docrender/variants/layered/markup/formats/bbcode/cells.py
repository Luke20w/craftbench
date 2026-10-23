from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY


@REGISTRY.cell("text", "bbcode")
class BBCodeText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "bbcode")
class BBCodeStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[b]" + ctx.inlines(node.children) + "[/b]"


@REGISTRY.cell("emphasis", "bbcode")
class BBCodeEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[i]" + ctx.inlines(node.children) + "[/i]"


@REGISTRY.cell("code", "bbcode")
class BBCodeCode(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[icode]" + ctx.escape(node.value) + "[/icode]"


@REGISTRY.cell("link", "bbcode")
class BBCodeLink(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[url=" + node.url + "]" + ctx.inlines(node.children) + "[/url]"


@REGISTRY.cell("line_break", "bbcode")
class BBCodeLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\n"


@REGISTRY.cell("subscript", "bbcode")
class BBCodeSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[sub]" + ctx.inlines(node.children) + "[/sub]"


@REGISTRY.cell("superscript", "bbcode")
class BBCodeSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[sup]" + ctx.inlines(node.children) + "[/sup]"


@REGISTRY.cell("highlight", "bbcode")
class BBCodeHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[highlight]" + ctx.inlines(node.children) + "[/highlight]"


@REGISTRY.cell("kbd", "bbcode")
class BBCodeKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[kbd]" + node.value + "[/kbd]"


@REGISTRY.cell("math", "bbcode")
class BBCodeMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[math]" + node.value + "[/math]"


@REGISTRY.cell("paragraph", "bbcode")
class BBCodeParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("heading", "bbcode")
class BBCodeHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        size = {1: 200, 2: 150}.get(node.level, 120)
        return f"[size={size}%][b]" + ctx.inlines(node.children) + "[/b][/size]"


@REGISTRY.cell("code_block", "bbcode")
class BBCodeCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        opening = "[code=" + node.language + "]" if node.language else "[code]"
        return opening + "\n" + node.code + "\n[/code]"


@REGISTRY.cell("quote", "bbcode")
class BBCodeQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[quote]\n" + ctx.blocks(node.children) + "\n[/quote]"


@REGISTRY.cell("list", "bbcode")
class BBCodeList(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = ["[list=1]" if node.ordered else "[list]"]
        for item in node.items:
            lines.append("[*]" + ctx.inlines(item.children))
            if item.sublist:
                lines.append(ctx.render(item.sublist))
        lines.append("[/list]")
        return "\n".join(lines)


@REGISTRY.cell("table", "bbcode")
class BBCodeTable(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = ["[table]", "[tr]" + "".join("[th]" + ctx.inlines(cell) + "[/th]" for cell in node.header) + "[/tr]"]
        for cells in node.rows:
            lines.append("[tr]" + "".join("[td]" + ctx.inlines(cell) + "[/td]" for cell in cells) + "[/tr]")
        lines.append("[/table]")
        return "\n".join(lines)


@REGISTRY.cell("rule", "bbcode")
class BBCodeRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[hr]"


@REGISTRY.cell("image", "bbcode")
class BBCodeImage(CellRenderer):
    def render(self, node, ctx) -> str:
        return '[img alt="' + node.alt.replace('"', "'") + '"]' + node.src + "[/img]"


@REGISTRY.cell("figure", "bbcode")
class BBCodeFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        return '[img alt="' + node.alt.replace('"', "'") + '"]' + node.src + "[/img]\n[i]" + ctx.inlines(node.caption) + "[/i]"
