from ...core.interfaces import FormatSpec
from ...core.registry import REGISTRY


@REGISTRY.format
class LatexFormat(FormatSpec):
    name = "latex"

    def escape(self, text: str) -> str:
        out = []
        for ch in text:
            if ch == "\\":
                out.append("\\textbackslash{}")
            elif ch in "&%$#_{}":
                out.append("\\" + ch)
            elif ch == "~":
                out.append("\\textasciitilde{}")
            elif ch == "^":
                out.append("\\textasciicircum{}")
            else:
                out.append(ch)
        return "".join(out)
