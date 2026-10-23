"""The change requests, as cells: new node kinds (one body per existing format) and new formats (one body per
existing kind). Used only to produce the expected outputs of the hidden tests."""

NEW_KINDS: dict[str, dict[str, str]] = {}
NEW_FORMATS: dict[str, dict[str, str]] = {}

NEW_KINDS["strikethrough"] = {
    "html": r'''return "<del>" + INL(N.children) + "</del>"''',
    "markdown": r'''return "~~" + INL(N.children) + "~~"''',
    "plain": r'''return "~" + INL(N.children) + "~"''',
    "latex": r'''return "\\sout{" + INL(N.children) + "}"''',
    "mediawiki": r'''return "<s>" + INL(N.children) + "</s>"''',
    "bbcode": r'''return "[s]" + INL(N.children) + "[/s]"''',
    "org": r'''return "+" + INL(N.children) + "+"''',
    "slack": r'''return "~" + INL(N.children) + "~"''',
    "jira": r'''return "-" + INL(N.children) + "-"''',
    "dokuwiki": r'''return "<del>" + INL(N.children) + "</del>"''',
    "creole": r'''return "--" + INL(N.children) + "--"''',
    "tiddlywiki": r'''return "~~" + INL(N.children) + "~~"''',
}

NEW_KINDS["callout"] = {
    "html": r'''return '<aside class="callout ' + N.variant + '">\n' + BLK(N.children) + "\n</aside>"''',
    "markdown": r'''return prefix_lines("[!" + N.variant.upper() + "]\n" + BLK(N.children), "> ")''',
    "plain": r'''return N.variant.upper() + ":\n" + prefix_lines(BLK(N.children), "  ")''',
    "latex": r'''return "\\begin{" + N.variant + "}\n" + BLK(N.children) + "\n\\end{" + N.variant + "}"''',
    "mediawiki": r'''return "{{" + N.variant.capitalize() + "|1=\n" + BLK(N.children) + "\n}}"''',
    "bbcode": r'''return "[quote=" + N.variant.capitalize() + "]\n" + BLK(N.children) + "\n[/quote]"''',
    "org": r'''return "#+BEGIN_" + N.variant.upper() + "\n" + BLK(N.children) + "\n#+END_" + N.variant.upper()''',
    "slack": r'''
icon = {"note": ":information_source:", "warning": ":warning:", "tip": ":bulb:"}[N.variant]
return prefix_lines(icon + " *" + N.variant.capitalize() + "*\n" + BLK(N.children), "> ")
''',
    "jira": r'''return "{panel:title=" + N.variant.capitalize() + "}\n" + BLK(N.children) + "\n{panel}"''',
    "dokuwiki": r'''return "<WRAP " + N.variant + ">\n" + BLK(N.children) + "\n</WRAP>"''',
    "creole": r'''return prefix_lines(N.variant.upper() + ":\n" + BLK(N.children), "> ")''',
    "tiddlywiki": r'''return "@@." + N.variant + "\n" + BLK(N.children) + "\n@@"''',
}

NEW_KINDS["definition_list"] = {
    "html": r'''
entries = ["<dt>" + INL(item.term) + "</dt>\n<dd>" + BLK(item.definition) + "</dd>" for item in N.items]
return "<dl>\n" + "\n".join(entries) + "\n</dl>"
''',
    "markdown": r'''
return "\n\n".join(INL(item.term) + "\n" + prefix_lines(BLK(item.definition), ": ", "  ") for item in N.items)
''',
    "plain": r'''
return "\n".join(INL(item.term) + "\n" + prefix_lines(BLK(item.definition), "    ") for item in N.items)
''',
    "latex": r'''
entries = [prefix_lines("\\item[" + INL(item.term) + "] " + BLK(item.definition), "  ") for item in N.items]
return "\\begin{description}\n" + "\n".join(entries) + "\n\\end{description}"
''',
    "mediawiki": r'''
return "\n".join("; " + INL(item.term) + "\n" + prefix_lines(BLK(item.definition), ": ") for item in N.items)
''',
    "bbcode": r'''
return "\n".join("[b]" + INL(item.term) + "[/b]\n[indent]" + BLK(item.definition) + "[/indent]" for item in N.items)
''',
    "org": r'''
return "\n".join(prefix_lines(INL(item.term) + " :: " + BLK(item.definition), "- ", "  ") for item in N.items)
''',
    "slack": r'''
return "\n".join("*" + INL(item.term) + "*\n" + prefix_lines(BLK(item.definition), "    ") for item in N.items)
''',
    "jira": r'''
return "\n".join("*" + INL(item.term) + "*\n" + BLK(item.definition) for item in N.items)
''',
    "dokuwiki": r'''
return "\n".join(prefix_lines("**" + INL(item.term) + "**: " + BLK(item.definition), "  * ", "    ") for item in N.items)
''',
    "creole": r'''
return "\n".join(";" + INL(item.term) + "\n" + prefix_lines(BLK(item.definition), ":") for item in N.items)
''',
    "tiddlywiki": r'''
return "\n".join("; " + INL(item.term) + "\n" + prefix_lines(BLK(item.definition), ": ") for item in N.items)
''',
}

NEW_FORMATS["asciidoc"] = {
    "separator": "\n\n",
    "esc": r'''
if any(ch in text for ch in "*_`#^~+[]"):
    return "+++" + text + "+++"
return text
''',
    "text": r'''return ESC(N.value)''',
    "strong": r'''return "*" + INL(N.children) + "*"''',
    "emphasis": r'''return "_" + INL(N.children) + "_"''',
    "code": r'''return "`+" + N.value + "+`"''',
    "link": r'''return N.url + "[" + INL(N.children) + "]"''',
    "line_break": r'''return " +\n"''',
    "paragraph": r'''return INL(N.children)''',
    "heading": r'''return "=" * (min(N.level, 5) + 1) + " " + INL(N.children)''',
    "code_block": r'''
header = "[source," + N.language + "]\n" if N.language else ""
return header + "----\n" + N.code + "\n----"
''',
    "quote": r'''return "____\n" + BLK(N.children) + "\n____"''',
    "list": r'''
marker = "." if N.ordered else "*"
lines = []
for item in N.items:
    lines.append(marker + " " + INL(item.children))
    if item.sublist:
        for line in R(item.sublist).split("\n"):
            lines.append(line[0] + line if line[:1] in ("*", ".") else line)
return "\n".join(lines)
''',
    "table": r'''
lines = ["|===", "| " + " | ".join(INL(cell) for cell in N.header), ""]
lines += ["| " + " | ".join(INL(cell) for cell in cells) for cells in N.rows]
lines.append("|===")
return "\n".join(lines)
''',
    "rule": r'''return "\'\'\'"''',
    "image": r'''return "image::" + N.src + "[" + N.alt + "]"''',
}

NEW_FORMATS["textile"] = {
    "separator": "\n\n",
    "esc": r'''
if any(ch in text for ch in "*_+-^~@%!|"):
    return "==" + text + "=="
return text
''',
    "text": r'''return ESC(N.value)''',
    "strong": r'''return "*" + INL(N.children) + "*"''',
    "emphasis": r'''return "_" + INL(N.children) + "_"''',
    "code": r'''return "@" + N.value + "@"''',
    "link": r'''return '"' + INL(N.children) + '":' + N.url''',
    "line_break": r'''return "\n"''',
    "paragraph": r'''return INL(N.children)''',
    "heading": r'''return f"h{min(N.level, 6)}. " + INL(N.children)''',
    "code_block": r'''
opening = "bc(language-" + N.language + ").. " if N.language else "bc.. "
return opening + N.code
''',
    "quote": r'''return "bq.. " + BLK(N.children)''',
    "list": r'''
marker = "#" if N.ordered else "*"
lines = []
for item in N.items:
    lines.append(marker + " " + INL(item.children))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), marker))
return "\n".join(lines)
''',
    "table": r'''
lines = ["|" + "|".join("_. " + INL(cell) for cell in N.header) + "|"]
lines += ["|" + "|".join(INL(cell) for cell in cells) + "|" for cells in N.rows]
return "\n".join(lines)
''',
    "rule": r'''return "---"''',
    "image": r'''return "!" + N.src + ("(" + N.alt + ")" if N.alt else "") + "!"''',
}

NEW_FORMATS["rst"] = {
    "separator": "\n\n",
    "esc": r'''
for ch in "\\*`_|":
    text = text.replace(ch, "\\" + ch)
return text
''',
    "text": r'''return ESC(N.value)''',
    "strong": r'''return "**" + INL(N.children) + "**"''',
    "emphasis": r'''return "*" + INL(N.children) + "*"''',
    "code": r'''return "``" + N.value + "``"''',
    "link": r'''return "`" + INL(N.children) + " <" + N.url + ">`_"''',
    "line_break": r'''return " "''',
    "paragraph": r'''return INL(N.children)''',
    "heading": r'''
text = INL(N.children)
underline = {1: "=", 2: "-", 3: "~"}.get(N.level, "^")
return text + "\n" + underline * len(text)
''',
    "code_block": r'''
directive = ".. code-block:: " + N.language if N.language else "::"
return directive + "\n\n" + prefix_lines(N.code, "   ")
''',
    "quote": r'''return prefix_lines(BLK(N.children), "    ")''',
    "list": r'''
lines = []
for number, item in enumerate(N.items, 1):
    marker = f"{number}. " if N.ordered else "- "
    lines.append(prefix_lines(INL(item.children), marker, " " * len(marker)))
    if item.sublist:
        lines += ["", prefix_lines(R(item.sublist), " " * len(marker)), ""]
return "\n".join(lines).rstrip("\n")
''',
    "table": r'''
rows = [[INL(cell) for cell in N.header]] + [[INL(cell) for cell in cells] for cells in N.rows]
widths = [max(len(cells[i]) for cells in rows) for i in range(len(N.header))]
border = "  ".join("=" * width for width in widths)
def line(cells):
    return "  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()
return "\n".join([border, line(rows[0]), border] + [line(cells) for cells in rows[1:]] + [border])
''',
    "rule": r'''return "----"''',
    "image": r'''return ".. image:: " + N.src + ("\n   :alt: " + N.alt if N.alt else "")''',
}

NEW_FORMATS["asciidoc"].update({
    "subscript": r'''return "~" + INL(N.children) + "~"''',
    "superscript": r'''return "^" + INL(N.children) + "^"''',
    "highlight": r'''return "#" + INL(N.children) + "#"''',
    "kbd": r'''return "kbd:[" + N.value + "]"''',
    "math": r'''return "stem:[" + N.value + "]"''',
    "figure": r'''return "." + INL(N.caption) + "\nimage::" + N.src + "[" + N.alt + "]"''',
})
NEW_FORMATS["textile"].update({
    "subscript": r'''return "~" + INL(N.children) + "~"''',
    "superscript": r'''return "^" + INL(N.children) + "^"''',
    "highlight": r'''return "%{background:yellow}" + INL(N.children) + "%"''',
    "kbd": r'''return "<kbd>" + N.value + "</kbd>"''',
    "math": r'''return "@" + N.value + "@"''',
    "figure": r'''return "!" + N.src + ("(" + N.alt + ")" if N.alt else "") + "!\np(caption). " + INL(N.caption)''',
})
NEW_FORMATS["rst"].update({
    "subscript": r'''return ":sub:`" + INL(N.children) + "`"''',
    "superscript": r'''return ":sup:`" + INL(N.children) + "`"''',
    "highlight": r'''return ":mark:`" + INL(N.children) + "`"''',
    "kbd": r'''return ":kbd:`" + N.value + "`"''',
    "math": r'''return ":math:`" + N.value + "`"''',
    "figure": r'''
alt = "\n   :alt: " + N.alt if N.alt else ""
return ".. figure:: " + N.src + alt + "\n\n   " + INL(N.caption)
''',
})


# ---- stream S: changes to behaviour the formats share. Each adds an optional field, so documents without it
# render as before. MODIFIED[change][format][kind] is the new rule.
def _modified() -> dict[str, dict[str, dict[str, str]]]:
    from cells import FORMATS

    out: dict[str, dict[str, dict[str, str]]] = {"list_start": {}, "quote_cite": {}, "default_alt": {}}
    for fmt, cells in FORMATS.items():
        if "enumerate(N.items, 1)" in cells["list"]:
            out["list_start"][fmt] = {"list": cells["list"].replace(
                "enumerate(N.items, 1)", 'enumerate(N.items, getattr(N, "start", 1))')}
        attribution = '"\\n<footer>— " + INL(N.cite) + "</footer>"' if fmt == "html" else '"\\n\\n— " + INL(N.cite)'
        out["quote_cite"][fmt] = {"quote": 'body = BLK(N.children)\nif getattr(N, "cite", None):\n    body += ' + attribution
                                  + "\n" + cells["quote"].strip("\n").replace("BLK(N.children)", "body")}
        for kind in ("image", "figure"):
            if "N.alt" in cells[kind]:
                out["default_alt"].setdefault(fmt, {})[kind] = (
                    'alt = getattr(N, "alt", None)\nif alt is None:\n    alt = N.src.rsplit("/", 1)[-1]\n'
                    + cells[kind].strip("\n").replace("N.alt", "alt"))
    out["list_start"]["html"] = {"list": r'''
tag = "ol" if N.ordered else "ul"
start = getattr(N, "start", 1)
attr = f' start="{start}"' if N.ordered and start != 1 else ""
items = []
for item in N.items:
    body = INL(item.children)
    if item.sublist:
        body += "\n" + R(item.sublist)
    items.append("<li>" + body + "</li>")
return f"<{tag}{attr}>\n" + "\n".join(items) + f"\n</{tag}>"
'''}
    out["list_start"]["latex"] = {"list": r'''
env = "enumerate" if N.ordered else "itemize"
start = getattr(N, "start", 1)
lines = ["\\begin{" + env + "}"]
if N.ordered and start != 1:
    lines.append("  \\setcounter{enumi}{" + str(start - 1) + "}")
for item in N.items:
    lines.append(prefix_lines(INL(item.children), "  \\item ", "  "))
    if item.sublist:
        lines.append(prefix_lines(R(item.sublist), "  "))
lines.append("\\end{" + env + "}")
return "\n".join(lines)
'''}
    out["list_start"]["bbcode"] = {"list": r'''
lines = ["[list=" + str(getattr(N, "start", 1)) + "]" if N.ordered else "[list]"]
for item in N.items:
    lines.append("[*]" + INL(item.children))
    if item.sublist:
        lines.append(R(item.sublist))
lines.append("[/list]")
return "\n".join(lines)
'''}
    return out


MODIFIED = _modified()
