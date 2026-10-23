"""The rendering rules, one function body per (format, node kind). Every variant is emitted from these, so all
variants behave identically and differ only in how the code is organized.

Placeholders, replaced per variant: N (the node), ESC(text), INL(inline children), BLK(block children),
R(node). `prefix_lines` is a shared text helper available in every variant.
"""

import re

INLINE = ["text", "strong", "emphasis", "code", "link", "line_break", "subscript", "superscript", "highlight", "kbd",
          "math"]
BLOCK = ["paragraph", "heading", "code_block", "quote", "list", "table", "rule", "image", "figure"]
KINDS = INLINE + BLOCK

FORMATS: dict[str, dict[str, str]] = {}

FORMATS["html"] = {
    "separator": "\n",
    "esc": r"""
return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
""",
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return "<strong>" + INL(N.children) + "</strong>"
""",
    "emphasis": r"""
return "<em>" + INL(N.children) + "</em>"
""",
    "code": r"""
return "<code>" + ESC(N.value) + "</code>"
""",
    "link": r"""
return '<a href="' + ESC(N.url) + '">' + INL(N.children) + "</a>"
""",
    "line_break": r"""
return "<br>"
""",
    "paragraph": r"""
return "<p>" + INL(N.children) + "</p>"
""",
    "heading": r"""
level = min(N.level, 6)
return f"<h{level}>" + INL(N.children) + f"</h{level}>"
""",
    "code_block": r"""
attr = ' class="language-' + ESC(N.language) + '"' if N.language else ""
return "<pre><code" + attr + ">" + ESC(N.code) + "</code></pre>"
""",
    "quote": r"""
return "<blockquote>\n" + BLK(N.children) + "\n</blockquote>"
""",
    "list": r"""
tag = "ol" if N.ordered else "ul"
items = []
for item in N.items:
    body = INL(item.children)
    if item.sublist:
        body += "\n" + R(item.sublist)
    items.append("<li>" + body + "</li>")
return f"<{tag}>\n" + "\n".join(items) + f"\n</{tag}>"
""",
    "table": r"""
lines = ["<table>", "<tr>" + "".join("<th>" + INL(cell) + "</th>" for cell in N.header) + "</tr>"]
for row in N.rows:
    lines.append("<tr>" + "".join("<td>" + INL(cell) + "</td>" for cell in row) + "</tr>")
lines.append("</table>")
return "\n".join(lines)
""",
    "rule": r"""
return "<hr>"
""",
    "image": r"""
return '<img src="' + ESC(N.src) + '" alt="' + ESC(N.alt) + '">'
""",
}

FORMATS["markdown"] = {
    "separator": "\n\n",
    "esc": r"""
for ch in "\\`*_[]#|":
    text = text.replace(ch, "\\" + ch)
return text
""",
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return "**" + INL(N.children) + "**"
""",
    "emphasis": r"""
return "*" + INL(N.children) + "*"
""",
    "code": r"""
if "`" in N.value:
    return "`` " + N.value + " ``"
return "`" + N.value + "`"
""",
    "link": r"""
url = N.url.replace(" ", "%20").replace(")", "%29")
return "[" + INL(N.children) + "](" + url + ")"
""",
    "line_break": r"""
return "\\\n"
""",
    "paragraph": r"""
return INL(N.children)
""",
    "heading": r"""
return "#" * min(N.level, 6) + " " + INL(N.children)
""",
    "code_block": r"""
fence = "````" if "```" in N.code else "```"
return fence + N.language + "\n" + N.code + "\n" + fence
""",
    "quote": r"""
return prefix_lines(BLK(N.children), "> ")
""",
    "list": r"""
lines = []
for number, item in enumerate(N.items, 1):
    marker = f"{number}. " if N.ordered else "- "
    lines.append(prefix_lines(INL(item.children), marker, " " * len(marker)))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), " " * len(marker)))
return "\n".join(lines)
""",
    "table": r"""
def row(cells):
    return "| " + " | ".join(INL(cell) for cell in cells) + " |"
lines = [row(N.header), "|" + "|".join(" --- " for _ in N.header) + "|"]
lines += [row(cells) for cells in N.rows]
return "\n".join(lines)
""",
    "rule": r"""
return "---"
""",
    "image": r"""
return "![" + ESC(N.alt) + "](" + N.src.replace(" ", "%20").replace(")", "%29") + ")"
""",
}

FORMATS["plain"] = {
    "separator": "\n\n",
    "esc": r"""
return text
""",
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return INL(N.children).upper()
""",
    "emphasis": r"""
return "_" + INL(N.children) + "_"
""",
    "code": r"""
return N.value
""",
    "link": r"""
text = INL(N.children)
return text if text == N.url else text + " <" + N.url + ">"
""",
    "line_break": r"""
return "\n"
""",
    "paragraph": r"""
return INL(N.children)
""",
    "heading": r"""
text = INL(N.children)
if N.level == 1:
    return text + "\n" + "=" * len(text)
if N.level == 2:
    return text + "\n" + "-" * len(text)
return text
""",
    "code_block": r"""
return prefix_lines(N.code, "    ")
""",
    "quote": r"""
return prefix_lines(BLK(N.children), "| ")
""",
    "list": r"""
lines = []
for number, item in enumerate(N.items, 1):
    marker = f"{number}) " if N.ordered else "* "
    lines.append(prefix_lines(INL(item.children), marker, " " * len(marker)))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), " " * len(marker)))
return "\n".join(lines)
""",
    "table": r"""
rows = [[INL(cell) for cell in N.header]] + [[INL(cell) for cell in cells] for cells in N.rows]
widths = [max(len(cells[i]) for cells in rows) for i in range(len(N.header))]
def line(cells):
    return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()
lines = [line(rows[0]), "-+-".join("-" * width for width in widths)]
lines += [line(cells) for cells in rows[1:]]
return "\n".join(lines)
""",
    "rule": r"""
return "* * *"
""",
    "image": r"""
return "[image: " + N.alt + "]"
""",
}

FORMATS["latex"] = {
    "separator": "\n\n",
    "esc": r"""
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
""",
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return "\\textbf{" + INL(N.children) + "}"
""",
    "emphasis": r"""
return "\\emph{" + INL(N.children) + "}"
""",
    "code": r"""
return "\\texttt{" + ESC(N.value) + "}"
""",
    "link": r"""
url = N.url.replace("%", "\\%").replace("#", "\\#")
return "\\href{" + url + "}{" + INL(N.children) + "}"
""",
    "line_break": r"""
return "\\\\\n"
""",
    "paragraph": r"""
return INL(N.children)
""",
    "heading": r"""
command = {1: "section", 2: "subsection"}.get(N.level, "subsubsection")
return "\\" + command + "{" + INL(N.children) + "}"
""",
    "code_block": r"""
return "\\begin{verbatim}\n" + N.code + "\n\\end{verbatim}"
""",
    "quote": r"""
return "\\begin{quote}\n" + BLK(N.children) + "\n\\end{quote}"
""",
    "list": r"""
env = "enumerate" if N.ordered else "itemize"
lines = ["\\begin{" + env + "}"]
for item in N.items:
    lines.append(prefix_lines(INL(item.children), "  \\item ", "  "))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), "  "))
lines.append("\\end{" + env + "}")
return "\n".join(lines)
""",
    "table": r"""
columns = "|" + "|".join("l" for _ in N.header) + "|"
lines = ["\\begin{tabular}{" + columns + "}", "\\hline", " & ".join(INL(cell) for cell in N.header) + " \\\\", "\\hline"]
for cells in N.rows:
    lines.append(" & ".join(INL(cell) for cell in cells) + " \\\\")
lines += ["\\hline", "\\end{tabular}"]
return "\n".join(lines)
""",
    "rule": r"""
return "\\noindent\\rule{\\linewidth}{0.4pt}"
""",
    "image": r"""
return "\\includegraphics{" + N.src + "}"
""",
}

FORMATS["mediawiki"] = {
    "separator": "\n\n",
    "esc": r"""
for ch, entity in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("[", "&#91;"), ("]", "&#93;")):
    text = text.replace(ch, entity)
return text
""",
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return "'''" + INL(N.children) + "'''"
""",
    "emphasis": r"""
return "''" + INL(N.children) + "''"
""",
    "code": r"""
return "<code>" + ESC(N.value) + "</code>"
""",
    "link": r"""
return "[" + N.url + " " + INL(N.children) + "]"
""",
    "line_break": r"""
return "<br />"
""",
    "paragraph": r"""
return INL(N.children)
""",
    "heading": r"""
marks = "=" * (min(N.level, 5) + 1)
return marks + " " + INL(N.children) + " " + marks
""",
    "code_block": r"""
if N.language:
    return '<syntaxhighlight lang="' + N.language + '">\n' + N.code + "\n</syntaxhighlight>"
return "<pre>\n" + ESC(N.code) + "\n</pre>"
""",
    "quote": r"""
return "<blockquote>\n" + BLK(N.children) + "\n</blockquote>"
""",
    "list": r"""
marker = "#" if N.ordered else "*"
lines = []
for item in N.items:
    lines.append(marker + " " + INL(item.children))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), marker))
return "\n".join(lines)
""",
    "table": r"""
lines = ['{| class="wikitable"', "! " + " !! ".join(INL(cell) for cell in N.header)]
for cells in N.rows:
    lines += ["|-", "| " + " || ".join(INL(cell) for cell in cells)]
lines.append("|}")
return "\n".join(lines)
""",
    "rule": r"""
return "----"
""",
    "image": r"""
return "[[File:" + N.src + "|" + ESC(N.alt) + "]]"
""",
}

FORMATS["bbcode"] = {
    "separator": "\n\n",
    "esc": r"""
return "[noparse]" + text + "[/noparse]" if "[" in text else text
""",
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return "[b]" + INL(N.children) + "[/b]"
""",
    "emphasis": r"""
return "[i]" + INL(N.children) + "[/i]"
""",
    "code": r"""
return "[icode]" + ESC(N.value) + "[/icode]"
""",
    "link": r"""
return "[url=" + N.url + "]" + INL(N.children) + "[/url]"
""",
    "line_break": r"""
return "\n"
""",
    "paragraph": r"""
return INL(N.children)
""",
    "heading": r"""
size = {1: 200, 2: 150}.get(N.level, 120)
return f"[size={size}%][b]" + INL(N.children) + "[/b][/size]"
""",
    "code_block": r"""
opening = "[code=" + N.language + "]" if N.language else "[code]"
return opening + "\n" + N.code + "\n[/code]"
""",
    "quote": r"""
return "[quote]\n" + BLK(N.children) + "\n[/quote]"
""",
    "list": r"""
lines = ["[list=1]" if N.ordered else "[list]"]
for item in N.items:
    lines.append("[*]" + INL(item.children))
    if item.sublist:
        lines.append(R(item.sublist))
lines.append("[/list]")
return "\n".join(lines)
""",
    "table": r"""
lines = ["[table]", "[tr]" + "".join("[th]" + INL(cell) + "[/th]" for cell in N.header) + "[/tr]"]
for cells in N.rows:
    lines.append("[tr]" + "".join("[td]" + INL(cell) + "[/td]" for cell in cells) + "[/tr]")
lines.append("[/table]")
return "\n".join(lines)
""",
    "rule": r"""
return "[hr]"
""",
    "image": r"""
return '[img alt="' + N.alt.replace('"', "'") + '"]' + N.src + "[/img]"
""",
}

FORMATS["org"] = {
    "separator": "\n\n",
    "esc": r"""
return text.replace("[[", "[\u200b[")
""",
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return "*" + INL(N.children) + "*"
""",
    "emphasis": r"""
return "/" + INL(N.children) + "/"
""",
    "code": r"""
return "~" + N.value + "~"
""",
    "link": r"""
return "[[" + N.url + "][" + INL(N.children) + "]]"
""",
    "line_break": r"""
return "\\\\\n"
""",
    "paragraph": r"""
return INL(N.children)
""",
    "heading": r"""
return "*" * N.level + " " + INL(N.children)
""",
    "code_block": r"""
opening = "#+BEGIN_SRC " + N.language if N.language else "#+BEGIN_SRC"
return opening + "\n" + N.code + "\n#+END_SRC"
""",
    "quote": r"""
return "#+BEGIN_QUOTE\n" + BLK(N.children) + "\n#+END_QUOTE"
""",
    "list": r"""
lines = []
for number, item in enumerate(N.items, 1):
    marker = f"{number}. " if N.ordered else "- "
    lines.append(prefix_lines(INL(item.children), marker, " " * len(marker)))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), " " * len(marker)))
return "\n".join(lines)
""",
    "table": r"""
def row(cells):
    return "| " + " | ".join(INL(cell) for cell in cells) + " |"
lines = [row(N.header), "|" + "+".join("---" for _ in N.header) + "|"]
lines += [row(cells) for cells in N.rows]
return "\n".join(lines)
""",
    "rule": r"""
return "-----"
""",
    "image": r"""
caption = "#+CAPTION: " + N.alt + "\n" if N.alt else ""
return caption + "[[" + N.src + "]]"
""",
}

FORMATS["slack"] = {
    "separator": "\n\n",
    "esc": r"""
return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
""",
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return "*" + INL(N.children) + "*"
""",
    "emphasis": r"""
return "_" + INL(N.children) + "_"
""",
    "code": r"""
return "`" + N.value + "`"
""",
    "link": r"""
return "<" + N.url + "|" + INL(N.children) + ">"
""",
    "line_break": r"""
return "\n"
""",
    "paragraph": r"""
return INL(N.children)
""",
    "heading": r"""
return "*" + INL(N.children) + "*"
""",
    "code_block": r"""
return "```\n" + N.code + "\n```"
""",
    "quote": r"""
return prefix_lines(BLK(N.children), "> ")
""",
    "list": r"""
lines = []
for number, item in enumerate(N.items, 1):
    marker = f"{number}. " if N.ordered else "• "
    lines.append(prefix_lines(INL(item.children), marker, "    "))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), "    "))
return "\n".join(lines)
""",
    "table": r"""
rows = [[INL(cell) for cell in N.header]] + [[INL(cell) for cell in cells] for cells in N.rows]
widths = [max(len(cells[i]) for cells in rows) for i in range(len(N.header))]
lines = ["  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip() for cells in rows]
return "```\n" + "\n".join(lines) + "\n```"
""",
    "rule": r"""
return "----------"
""",
    "image": r"""
return "<" + N.src + "|" + (N.alt or N.src) + ">"
""",
}

FORMATS["jira"] = {
    "separator": "\n\n",
    "esc": r"""
for ch in "\\*_{}[]|":
    text = text.replace(ch, "\\" + ch)
return text
""",
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return "*" + INL(N.children) + "*"
""",
    "emphasis": r"""
return "_" + INL(N.children) + "_"
""",
    "code": r"""
return "{{" + N.value + "}}"
""",
    "link": r"""
return "[" + INL(N.children) + "|" + N.url + "]"
""",
    "line_break": r"""
return "\n"
""",
    "paragraph": r"""
return INL(N.children)
""",
    "heading": r"""
return f"h{min(N.level, 6)}. " + INL(N.children)
""",
    "code_block": r"""
opening = "{code:" + N.language + "}" if N.language else "{code}"
return opening + "\n" + N.code + "\n{code}"
""",
    "quote": r"""
return "{quote}\n" + BLK(N.children) + "\n{quote}"
""",
    "list": r"""
marker = "#" if N.ordered else "*"
lines = []
for item in N.items:
    lines.append(marker + " " + INL(item.children))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), marker))
return "\n".join(lines)
""",
    "table": r"""
lines = ["||" + "||".join(INL(cell) for cell in N.header) + "||"]
lines += ["|" + "|".join(INL(cell) for cell in cells) + "|" for cells in N.rows]
return "\n".join(lines)
""",
    "rule": r"""
return "----"
""",
    "image": r"""
return "!" + N.src + "|alt=" + N.alt + "!" if N.alt else "!" + N.src + "!"
""",
}

FORMATS["dokuwiki"] = {
    "separator": "\n\n",
    "esc": r"""
if any(ch in text for ch in "*/[]_'^|<>{}"):
    return "%%" + text + "%%"
return text
""",
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return "**" + INL(N.children) + "**"
""",
    "emphasis": r"""
return "//" + INL(N.children) + "//"
""",
    "code": r"""
return "''" + N.value + "''"
""",
    "link": r"""
return "[[" + N.url + "|" + INL(N.children) + "]]"
""",
    "line_break": r"""
return "\\\\ "
""",
    "paragraph": r"""
return INL(N.children)
""",
    "heading": r"""
marks = "=" * (7 - min(N.level, 5))
return marks + " " + INL(N.children) + " " + marks
""",
    "code_block": r"""
opening = "<code " + N.language + ">" if N.language else "<code>"
return opening + "\n" + N.code + "\n</code>"
""",
    "quote": r"""
return prefix_lines(BLK(N.children), "> ")
""",
    "list": r"""
marker = "  - " if N.ordered else "  * "
lines = []
for item in N.items:
    lines.append(marker + INL(item.children))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), "  "))
return "\n".join(lines)
""",
    "table": r"""
lines = ["^ " + " ^ ".join(INL(cell) for cell in N.header) + " ^"]
lines += ["| " + " | ".join(INL(cell) for cell in cells) + " |" for cells in N.rows]
return "\n".join(lines)
""",
    "rule": r"""
return "----"
""",
    "image": r"""
return "{{" + N.src + "|" + N.alt + "}}"
""",
}

FORMATS["creole"] = {
    "separator": "\n\n",
    "esc": r"""
for ch in "~*/[]{}\\|=#":
    text = text.replace(ch, "~" + ch)
return text
""",
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return "**" + INL(N.children) + "**"
""",
    "emphasis": r"""
return "//" + INL(N.children) + "//"
""",
    "code": r"""
return "{{{" + N.value + "}}}"
""",
    "link": r"""
return "[[" + N.url + "|" + INL(N.children) + "]]"
""",
    "line_break": r"""
return "\\\\"
""",
    "paragraph": r"""
return INL(N.children)
""",
    "heading": r"""
return "=" * min(N.level, 6) + " " + INL(N.children)
""",
    "code_block": r"""
return "{{{\n" + N.code + "\n}}}"
""",
    "quote": r"""
return prefix_lines(BLK(N.children), "> ")
""",
    "list": r"""
marker = "#" if N.ordered else "*"
lines = []
for item in N.items:
    lines.append(marker + " " + INL(item.children))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), marker))
return "\n".join(lines)
""",
    "table": r"""
lines = ["|=" + "|=".join(INL(cell) for cell in N.header) + "|"]
lines += ["|" + "|".join(INL(cell) for cell in cells) + "|" for cells in N.rows]
return "\n".join(lines)
""",
    "rule": r"""
return "----"
""",
    "image": r"""
return "{{" + N.src + "|" + N.alt + "}}"
""",
}

FORMATS["tiddlywiki"] = {
    "separator": "\n\n",
    "esc": r'''
if any(ch in text for ch in "'/`[]{}<>^~_$|"):
    return '"""' + text + '"""'
return text
''',
    "text": r"""
return ESC(N.value)
""",
    "strong": r"""
return "''" + INL(N.children) + "''"
""",
    "emphasis": r"""
return "//" + INL(N.children) + "//"
""",
    "code": r"""
return "`" + N.value + "`"
""",
    "link": r"""
return "[[" + INL(N.children) + "|" + N.url + "]]"
""",
    "line_break": r"""
return "<br>"
""",
    "paragraph": r"""
return INL(N.children)
""",
    "heading": r"""
return "!" * min(N.level, 6) + " " + INL(N.children)
""",
    "code_block": r"""
return "```" + N.language + "\n" + N.code + "\n```"
""",
    "quote": r"""
return "<<<\n" + BLK(N.children) + "\n<<<"
""",
    "list": r"""
marker = "#" if N.ordered else "*"
lines = []
for item in N.items:
    lines.append(marker + " " + INL(item.children))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), marker))
return "\n".join(lines)
""",
    "table": r"""
lines = ["|!" + "|!".join(INL(cell) for cell in N.header) + "|"]
lines += ["|" + "|".join(INL(cell) for cell in cells) + "|" for cells in N.rows]
return "\n".join(lines)
""",
    "rule": r"""
return "---"
""",
    "image": r"""
return "[img[" + N.alt + "|" + N.src + "]]" if N.alt else "[img[" + N.src + "]]"
""",
}

def q(text: str) -> str:
    """A string literal in the double-quoted style of the cells above."""
    return repr(text) if '"' in text else '"' + text.replace("\\", "\\\\") + '"'


# Inline wrappers: (opening, closing) around the rendered children, per format.
for kind, marks in {
    "subscript": {"html": ("<sub>", "</sub>"), "markdown": ("<sub>", "</sub>"), "plain": ("_", ""),
                  "latex": ("\\textsubscript{", "}"), "mediawiki": ("<sub>", "</sub>"), "bbcode": ("[sub]", "[/sub]"),
                  "org": ("_{", "}"), "slack": ("", ""), "jira": ("~", "~"), "dokuwiki": ("<sub>", "</sub>"),
                  "creole": (",,", ",,"), "tiddlywiki": (",,", ",,")},
    "superscript": {"html": ("<sup>", "</sup>"), "markdown": ("<sup>", "</sup>"), "plain": ("^", ""),
                    "latex": ("\\textsuperscript{", "}"), "mediawiki": ("<sup>", "</sup>"), "bbcode": ("[sup]", "[/sup]"),
                    "org": ("^{", "}"), "slack": ("", ""), "jira": ("^", "^"), "dokuwiki": ("<sup>", "</sup>"),
                    "creole": ("^^", "^^"), "tiddlywiki": ("^^", "^^")},
    "highlight": {"html": ("<mark>", "</mark>"), "markdown": ("==", "=="), "plain": (">>", "<<"),
                  "latex": ("\\hl{", "}"), "mediawiki": ("<mark>", "</mark>"), "bbcode": ("[highlight]", "[/highlight]"),
                  "org": ("@@html:<mark>@@", "@@html:</mark>@@"), "slack": ("*_", "_*"),
                  "jira": ("{color:#ffab00}", "{color}"), "dokuwiki": ("<color black/yellow>", "</color>"),
                  "creole": ("__", "__"), "tiddlywiki": ("@@", "@@")},
}.items():
    for fmt, (opening, closing) in marks.items():
        FORMATS[fmt][kind] = "return " + (q(opening) + " + " if opening else "") + "INL(N.children)" + \
            (" + " + q(closing) if closing else "")

# Inline literals (`value`, not children): a template per format; <V> is the raw value, <E> the escaped value.
for kind, templates in {
    "kbd": {"html": "<kbd><E></kbd>", "markdown": "<kbd><V></kbd>", "plain": "[<V>]",
            "latex": "\\fbox{\\texttt{<E>}}", "mediawiki": "<kbd><E></kbd>", "bbcode": "[kbd]<V>[/kbd]",
            "org": "=<V>=", "slack": "`<V>`", "jira": "{{<V>}}", "dokuwiki": "<key><V></key>",
            "creole": "{{{<V>}}}", "tiddlywiki": "<kbd><V></kbd>"},
    "math": {"html": '<span class="math">\\(<E>\\)</span>', "markdown": "$<V>$", "plain": "<V>",
             "latex": "$<V>$", "mediawiki": "<math><V></math>", "bbcode": "[math]<V>[/math]",
             "org": "\\(<V>\\)", "slack": "`<V>`", "jira": "{{<V>}}", "dokuwiki": "$<V>$",
             "creole": "{{{<V>}}}", "tiddlywiki": "$$<V>$$"},
}.items():
    for fmt, template in templates.items():
        parts = [{"<V>": "N.value", "<E>": "ESC(N.value)"}.get(piece, q(piece))
                 for piece in re.split(r"(<V>|<E>)", template) if piece]
        FORMATS[fmt][kind] = "return " + " + ".join(parts)

FIGURES = {
    "html": r"""
return ('<figure>\n<img src="' + ESC(N.src) + '" alt="' + ESC(N.alt) + '">\n<figcaption>' + INL(N.caption)
        + "</figcaption>\n</figure>")
""",
    "markdown": r"""
return "![" + ESC(N.alt) + "](" + N.src.replace(" ", "%20").replace(")", "%29") + ")\n\n*" + INL(N.caption) + "*"
""",
    "plain": r"""
return "[image: " + N.alt + "]\n" + INL(N.caption)
""",
    "latex": r"""
return "\\begin{figure}\n\\includegraphics{" + N.src + "}\n\\caption{" + INL(N.caption) + "}\n\\end{figure}"
""",
    "mediawiki": r"""
return "[[File:" + N.src + "|thumb|" + INL(N.caption) + "]]"
""",
    "bbcode": r"""
return '[img alt="' + N.alt.replace('"', "'") + '"]' + N.src + "[/img]\n[i]" + INL(N.caption) + "[/i]"
""",
    "org": r"""
return "#+CAPTION: " + INL(N.caption) + "\n[[" + N.src + "]]"
""",
    "slack": r"""
return "<" + N.src + "|" + (N.alt or N.src) + ">\n_" + INL(N.caption) + "_"
""",
    "jira": r"""
image = "!" + N.src + "|alt=" + N.alt + "!" if N.alt else "!" + N.src + "!"
return image + "\n_" + INL(N.caption) + "_"
""",
    "dokuwiki": r"""
return "{{" + N.src + "|" + INL(N.caption) + "}}"
""",
    "creole": r"""
return "{{" + N.src + "|" + N.alt + "}}\n//" + INL(N.caption) + "//"
""",
    "tiddlywiki": r"""
image = "[img[" + N.alt + "|" + N.src + "]]" if N.alt else "[img[" + N.src + "]]"
return image + "\n//" + INL(N.caption) + "//"
""",
}
for fmt, cell in FIGURES.items():
    FORMATS[fmt]["figure"] = cell

assert all(set(cells) == set(KINDS) | {"separator", "esc"} for cells in FORMATS.values()), \
    {f: set(KINDS) ^ (set(c) - {"separator", "esc"}) for f, c in FORMATS.items()}
