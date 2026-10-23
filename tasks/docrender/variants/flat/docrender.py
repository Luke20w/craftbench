"""Render a JSON document tree to a markup format: python docrender.py --to html < doc.json"""
import argparse
import json
import sys

FORMATS = ['html', 'markdown', 'plain', 'latex', 'mediawiki', 'bbcode', 'org', 'slack', 'jira', 'dokuwiki', 'creole', 'tiddlywiki']
SEPARATORS = {"html": '\n', "markdown": '\n\n', "plain": '\n\n', "latex": '\n\n', "mediawiki": '\n\n', "bbcode": '\n\n', "org": '\n\n', "slack": '\n\n', "jira": '\n\n', "dokuwiki": '\n\n', "creole": '\n\n', "tiddlywiki": '\n\n'}


class RenderError(Exception):
    """A document that can't be rendered: unknown format, unknown node type."""


class Node:
    """A parsed JSON object: its fields become attributes, nested objects become Nodes."""

    def __init__(self, data):
        for key, value in data.items():
            setattr(self, key, build(value))


def build(value):
    if isinstance(value, dict):
        return Node(value)
    if isinstance(value, list):
        return [build(v) for v in value]
    return value


def prefix_lines(text, first, rest=None):
    """Prefix the first line of text with `first` and every later line with `rest` (default: `first`).
    Empty lines get the prefix without trailing spaces."""
    rest = first if rest is None else rest
    out = []
    for i, line in enumerate(text.split("\n")):
        prefix = first if i == 0 else rest
        out.append(prefix + line if line else prefix.rstrip())
    return "\n".join(out)


def escape(text, fmt):
    if fmt == "html":
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    elif fmt == "markdown":
        for ch in "\\`*_[]#|":
            text = text.replace(ch, "\\" + ch)
        return text
    elif fmt == "plain":
        return text
    elif fmt == "latex":
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
    elif fmt == "mediawiki":
        for ch, entity in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("[", "&#91;"), ("]", "&#93;")):
            text = text.replace(ch, entity)
        return text
    elif fmt == "bbcode":
        return "[noparse]" + text + "[/noparse]" if "[" in text else text
    elif fmt == "org":
        return text.replace("[[", "[\u200b[")
    elif fmt == "slack":
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    elif fmt == "jira":
        for ch in "\\*_{}[]|":
            text = text.replace(ch, "\\" + ch)
        return text
    elif fmt == "dokuwiki":
        if any(ch in text for ch in "*/[]_'^|<>{}"):
            return "%%" + text + "%%"
        return text
    elif fmt == "creole":
        for ch in "~*/[]{}\\|=#":
            text = text.replace(ch, "~" + ch)
        return text
    elif fmt == "tiddlywiki":
        if any(ch in text for ch in "'/`[]{}<>^~_$|"):
            return '"""' + text + '"""'
        return text
    return text


def render_inlines(children, fmt):
    return "".join(render(child, fmt) for child in children)


def render_blocks(children, fmt):
    return SEPARATORS[fmt].join(render(child, fmt) for child in children)


def render(node, fmt):
    if node.type == "document":
        return render_blocks(node.children, fmt) + "\n"
    if node.type == "text":
        if fmt == "html":
            return escape(node.value, fmt)
        elif fmt == "markdown":
            return escape(node.value, fmt)
        elif fmt == "plain":
            return escape(node.value, fmt)
        elif fmt == "latex":
            return escape(node.value, fmt)
        elif fmt == "mediawiki":
            return escape(node.value, fmt)
        elif fmt == "bbcode":
            return escape(node.value, fmt)
        elif fmt == "org":
            return escape(node.value, fmt)
        elif fmt == "slack":
            return escape(node.value, fmt)
        elif fmt == "jira":
            return escape(node.value, fmt)
        elif fmt == "dokuwiki":
            return escape(node.value, fmt)
        elif fmt == "creole":
            return escape(node.value, fmt)
        elif fmt == "tiddlywiki":
            return escape(node.value, fmt)
    if node.type == "strong":
        if fmt == "html":
            return "<strong>" + render_inlines(node.children, fmt) + "</strong>"
        elif fmt == "markdown":
            return "**" + render_inlines(node.children, fmt) + "**"
        elif fmt == "plain":
            return render_inlines(node.children, fmt).upper()
        elif fmt == "latex":
            return "\\textbf{" + render_inlines(node.children, fmt) + "}"
        elif fmt == "mediawiki":
            return "'''" + render_inlines(node.children, fmt) + "'''"
        elif fmt == "bbcode":
            return "[b]" + render_inlines(node.children, fmt) + "[/b]"
        elif fmt == "org":
            return "*" + render_inlines(node.children, fmt) + "*"
        elif fmt == "slack":
            return "*" + render_inlines(node.children, fmt) + "*"
        elif fmt == "jira":
            return "*" + render_inlines(node.children, fmt) + "*"
        elif fmt == "dokuwiki":
            return "**" + render_inlines(node.children, fmt) + "**"
        elif fmt == "creole":
            return "**" + render_inlines(node.children, fmt) + "**"
        elif fmt == "tiddlywiki":
            return "''" + render_inlines(node.children, fmt) + "''"
    if node.type == "emphasis":
        if fmt == "html":
            return "<em>" + render_inlines(node.children, fmt) + "</em>"
        elif fmt == "markdown":
            return "*" + render_inlines(node.children, fmt) + "*"
        elif fmt == "plain":
            return "_" + render_inlines(node.children, fmt) + "_"
        elif fmt == "latex":
            return "\\emph{" + render_inlines(node.children, fmt) + "}"
        elif fmt == "mediawiki":
            return "''" + render_inlines(node.children, fmt) + "''"
        elif fmt == "bbcode":
            return "[i]" + render_inlines(node.children, fmt) + "[/i]"
        elif fmt == "org":
            return "/" + render_inlines(node.children, fmt) + "/"
        elif fmt == "slack":
            return "_" + render_inlines(node.children, fmt) + "_"
        elif fmt == "jira":
            return "_" + render_inlines(node.children, fmt) + "_"
        elif fmt == "dokuwiki":
            return "//" + render_inlines(node.children, fmt) + "//"
        elif fmt == "creole":
            return "//" + render_inlines(node.children, fmt) + "//"
        elif fmt == "tiddlywiki":
            return "//" + render_inlines(node.children, fmt) + "//"
    if node.type == "code":
        if fmt == "html":
            return "<code>" + escape(node.value, fmt) + "</code>"
        elif fmt == "markdown":
            if "`" in node.value:
                return "`` " + node.value + " ``"
            return "`" + node.value + "`"
        elif fmt == "plain":
            return node.value
        elif fmt == "latex":
            return "\\texttt{" + escape(node.value, fmt) + "}"
        elif fmt == "mediawiki":
            return "<code>" + escape(node.value, fmt) + "</code>"
        elif fmt == "bbcode":
            return "[icode]" + escape(node.value, fmt) + "[/icode]"
        elif fmt == "org":
            return "~" + node.value + "~"
        elif fmt == "slack":
            return "`" + node.value + "`"
        elif fmt == "jira":
            return "{{" + node.value + "}}"
        elif fmt == "dokuwiki":
            return "''" + node.value + "''"
        elif fmt == "creole":
            return "{{{" + node.value + "}}}"
        elif fmt == "tiddlywiki":
            return "`" + node.value + "`"
    if node.type == "link":
        if fmt == "html":
            return '<a href="' + escape(node.url, fmt) + '">' + render_inlines(node.children, fmt) + "</a>"
        elif fmt == "markdown":
            url = node.url.replace(" ", "%20").replace(")", "%29")
            return "[" + render_inlines(node.children, fmt) + "](" + url + ")"
        elif fmt == "plain":
            text = render_inlines(node.children, fmt)
            return text if text == node.url else text + " <" + node.url + ">"
        elif fmt == "latex":
            url = node.url.replace("%", "\\%").replace("#", "\\#")
            return "\\href{" + url + "}{" + render_inlines(node.children, fmt) + "}"
        elif fmt == "mediawiki":
            return "[" + node.url + " " + render_inlines(node.children, fmt) + "]"
        elif fmt == "bbcode":
            return "[url=" + node.url + "]" + render_inlines(node.children, fmt) + "[/url]"
        elif fmt == "org":
            return "[[" + node.url + "][" + render_inlines(node.children, fmt) + "]]"
        elif fmt == "slack":
            return "<" + node.url + "|" + render_inlines(node.children, fmt) + ">"
        elif fmt == "jira":
            return "[" + render_inlines(node.children, fmt) + "|" + node.url + "]"
        elif fmt == "dokuwiki":
            return "[[" + node.url + "|" + render_inlines(node.children, fmt) + "]]"
        elif fmt == "creole":
            return "[[" + node.url + "|" + render_inlines(node.children, fmt) + "]]"
        elif fmt == "tiddlywiki":
            return "[[" + render_inlines(node.children, fmt) + "|" + node.url + "]]"
    if node.type == "line_break":
        if fmt == "html":
            return "<br>"
        elif fmt == "markdown":
            return "\\\n"
        elif fmt == "plain":
            return "\n"
        elif fmt == "latex":
            return "\\\\\n"
        elif fmt == "mediawiki":
            return "<br />"
        elif fmt == "bbcode":
            return "\n"
        elif fmt == "org":
            return "\\\\\n"
        elif fmt == "slack":
            return "\n"
        elif fmt == "jira":
            return "\n"
        elif fmt == "dokuwiki":
            return "\\\\ "
        elif fmt == "creole":
            return "\\\\"
        elif fmt == "tiddlywiki":
            return "<br>"
    if node.type == "subscript":
        if fmt == "html":
            return "<sub>" + render_inlines(node.children, fmt) + "</sub>"
        elif fmt == "markdown":
            return "<sub>" + render_inlines(node.children, fmt) + "</sub>"
        elif fmt == "plain":
            return "_" + render_inlines(node.children, fmt)
        elif fmt == "latex":
            return "\\textsubscript{" + render_inlines(node.children, fmt) + "}"
        elif fmt == "mediawiki":
            return "<sub>" + render_inlines(node.children, fmt) + "</sub>"
        elif fmt == "bbcode":
            return "[sub]" + render_inlines(node.children, fmt) + "[/sub]"
        elif fmt == "org":
            return "_{" + render_inlines(node.children, fmt) + "}"
        elif fmt == "slack":
            return render_inlines(node.children, fmt)
        elif fmt == "jira":
            return "~" + render_inlines(node.children, fmt) + "~"
        elif fmt == "dokuwiki":
            return "<sub>" + render_inlines(node.children, fmt) + "</sub>"
        elif fmt == "creole":
            return ",," + render_inlines(node.children, fmt) + ",,"
        elif fmt == "tiddlywiki":
            return ",," + render_inlines(node.children, fmt) + ",,"
    if node.type == "superscript":
        if fmt == "html":
            return "<sup>" + render_inlines(node.children, fmt) + "</sup>"
        elif fmt == "markdown":
            return "<sup>" + render_inlines(node.children, fmt) + "</sup>"
        elif fmt == "plain":
            return "^" + render_inlines(node.children, fmt)
        elif fmt == "latex":
            return "\\textsuperscript{" + render_inlines(node.children, fmt) + "}"
        elif fmt == "mediawiki":
            return "<sup>" + render_inlines(node.children, fmt) + "</sup>"
        elif fmt == "bbcode":
            return "[sup]" + render_inlines(node.children, fmt) + "[/sup]"
        elif fmt == "org":
            return "^{" + render_inlines(node.children, fmt) + "}"
        elif fmt == "slack":
            return render_inlines(node.children, fmt)
        elif fmt == "jira":
            return "^" + render_inlines(node.children, fmt) + "^"
        elif fmt == "dokuwiki":
            return "<sup>" + render_inlines(node.children, fmt) + "</sup>"
        elif fmt == "creole":
            return "^^" + render_inlines(node.children, fmt) + "^^"
        elif fmt == "tiddlywiki":
            return "^^" + render_inlines(node.children, fmt) + "^^"
    if node.type == "highlight":
        if fmt == "html":
            return "<mark>" + render_inlines(node.children, fmt) + "</mark>"
        elif fmt == "markdown":
            return "==" + render_inlines(node.children, fmt) + "=="
        elif fmt == "plain":
            return ">>" + render_inlines(node.children, fmt) + "<<"
        elif fmt == "latex":
            return "\\hl{" + render_inlines(node.children, fmt) + "}"
        elif fmt == "mediawiki":
            return "<mark>" + render_inlines(node.children, fmt) + "</mark>"
        elif fmt == "bbcode":
            return "[highlight]" + render_inlines(node.children, fmt) + "[/highlight]"
        elif fmt == "org":
            return "@@html:<mark>@@" + render_inlines(node.children, fmt) + "@@html:</mark>@@"
        elif fmt == "slack":
            return "*_" + render_inlines(node.children, fmt) + "_*"
        elif fmt == "jira":
            return "{color:#ffab00}" + render_inlines(node.children, fmt) + "{color}"
        elif fmt == "dokuwiki":
            return "<color black/yellow>" + render_inlines(node.children, fmt) + "</color>"
        elif fmt == "creole":
            return "__" + render_inlines(node.children, fmt) + "__"
        elif fmt == "tiddlywiki":
            return "@@" + render_inlines(node.children, fmt) + "@@"
    if node.type == "kbd":
        if fmt == "html":
            return "<kbd>" + escape(node.value, fmt) + "</kbd>"
        elif fmt == "markdown":
            return "<kbd>" + node.value + "</kbd>"
        elif fmt == "plain":
            return "[" + node.value + "]"
        elif fmt == "latex":
            return "\\fbox{\\texttt{" + escape(node.value, fmt) + "}}"
        elif fmt == "mediawiki":
            return "<kbd>" + escape(node.value, fmt) + "</kbd>"
        elif fmt == "bbcode":
            return "[kbd]" + node.value + "[/kbd]"
        elif fmt == "org":
            return "=" + node.value + "="
        elif fmt == "slack":
            return "`" + node.value + "`"
        elif fmt == "jira":
            return "{{" + node.value + "}}"
        elif fmt == "dokuwiki":
            return "<key>" + node.value + "</key>"
        elif fmt == "creole":
            return "{{{" + node.value + "}}}"
        elif fmt == "tiddlywiki":
            return "<kbd>" + node.value + "</kbd>"
    if node.type == "math":
        if fmt == "html":
            return '<span class="math">\\(' + escape(node.value, fmt) + "\\)</span>"
        elif fmt == "markdown":
            return "$" + node.value + "$"
        elif fmt == "plain":
            return node.value
        elif fmt == "latex":
            return "$" + node.value + "$"
        elif fmt == "mediawiki":
            return "<math>" + node.value + "</math>"
        elif fmt == "bbcode":
            return "[math]" + node.value + "[/math]"
        elif fmt == "org":
            return "\\(" + node.value + "\\)"
        elif fmt == "slack":
            return "`" + node.value + "`"
        elif fmt == "jira":
            return "{{" + node.value + "}}"
        elif fmt == "dokuwiki":
            return "$" + node.value + "$"
        elif fmt == "creole":
            return "{{{" + node.value + "}}}"
        elif fmt == "tiddlywiki":
            return "$$" + node.value + "$$"
    if node.type == "paragraph":
        if fmt == "html":
            return "<p>" + render_inlines(node.children, fmt) + "</p>"
        elif fmt == "markdown":
            return render_inlines(node.children, fmt)
        elif fmt == "plain":
            return render_inlines(node.children, fmt)
        elif fmt == "latex":
            return render_inlines(node.children, fmt)
        elif fmt == "mediawiki":
            return render_inlines(node.children, fmt)
        elif fmt == "bbcode":
            return render_inlines(node.children, fmt)
        elif fmt == "org":
            return render_inlines(node.children, fmt)
        elif fmt == "slack":
            return render_inlines(node.children, fmt)
        elif fmt == "jira":
            return render_inlines(node.children, fmt)
        elif fmt == "dokuwiki":
            return render_inlines(node.children, fmt)
        elif fmt == "creole":
            return render_inlines(node.children, fmt)
        elif fmt == "tiddlywiki":
            return render_inlines(node.children, fmt)
    if node.type == "heading":
        if fmt == "html":
            level = min(node.level, 6)
            return f"<h{level}>" + render_inlines(node.children, fmt) + f"</h{level}>"
        elif fmt == "markdown":
            return "#" * min(node.level, 6) + " " + render_inlines(node.children, fmt)
        elif fmt == "plain":
            text = render_inlines(node.children, fmt)
            if node.level == 1:
                return text + "\n" + "=" * len(text)
            if node.level == 2:
                return text + "\n" + "-" * len(text)
            return text
        elif fmt == "latex":
            command = {1: "section", 2: "subsection"}.get(node.level, "subsubsection")
            return "\\" + command + "{" + render_inlines(node.children, fmt) + "}"
        elif fmt == "mediawiki":
            marks = "=" * (min(node.level, 5) + 1)
            return marks + " " + render_inlines(node.children, fmt) + " " + marks
        elif fmt == "bbcode":
            size = {1: 200, 2: 150}.get(node.level, 120)
            return f"[size={size}%][b]" + render_inlines(node.children, fmt) + "[/b][/size]"
        elif fmt == "org":
            return "*" * node.level + " " + render_inlines(node.children, fmt)
        elif fmt == "slack":
            return "*" + render_inlines(node.children, fmt) + "*"
        elif fmt == "jira":
            return f"h{min(node.level, 6)}. " + render_inlines(node.children, fmt)
        elif fmt == "dokuwiki":
            marks = "=" * (7 - min(node.level, 5))
            return marks + " " + render_inlines(node.children, fmt) + " " + marks
        elif fmt == "creole":
            return "=" * min(node.level, 6) + " " + render_inlines(node.children, fmt)
        elif fmt == "tiddlywiki":
            return "!" * min(node.level, 6) + " " + render_inlines(node.children, fmt)
    if node.type == "code_block":
        if fmt == "html":
            attr = ' class="language-' + escape(node.language, fmt) + '"' if node.language else ""
            return "<pre><code" + attr + ">" + escape(node.code, fmt) + "</code></pre>"
        elif fmt == "markdown":
            fence = "````" if "```" in node.code else "```"
            return fence + node.language + "\n" + node.code + "\n" + fence
        elif fmt == "plain":
            return prefix_lines(node.code, "    ")
        elif fmt == "latex":
            return "\\begin{verbatim}\n" + node.code + "\n\\end{verbatim}"
        elif fmt == "mediawiki":
            if node.language:
                return '<syntaxhighlight lang="' + node.language + '">\n' + node.code + "\n</syntaxhighlight>"
            return "<pre>\n" + escape(node.code, fmt) + "\n</pre>"
        elif fmt == "bbcode":
            opening = "[code=" + node.language + "]" if node.language else "[code]"
            return opening + "\n" + node.code + "\n[/code]"
        elif fmt == "org":
            opening = "#+BEGIN_SRC " + node.language if node.language else "#+BEGIN_SRC"
            return opening + "\n" + node.code + "\n#+END_SRC"
        elif fmt == "slack":
            return "```\n" + node.code + "\n```"
        elif fmt == "jira":
            opening = "{code:" + node.language + "}" if node.language else "{code}"
            return opening + "\n" + node.code + "\n{code}"
        elif fmt == "dokuwiki":
            opening = "<code " + node.language + ">" if node.language else "<code>"
            return opening + "\n" + node.code + "\n</code>"
        elif fmt == "creole":
            return "{{{\n" + node.code + "\n}}}"
        elif fmt == "tiddlywiki":
            return "```" + node.language + "\n" + node.code + "\n```"
    if node.type == "quote":
        if fmt == "html":
            return "<blockquote>\n" + render_blocks(node.children, fmt) + "\n</blockquote>"
        elif fmt == "markdown":
            return prefix_lines(render_blocks(node.children, fmt), "> ")
        elif fmt == "plain":
            return prefix_lines(render_blocks(node.children, fmt), "| ")
        elif fmt == "latex":
            return "\\begin{quote}\n" + render_blocks(node.children, fmt) + "\n\\end{quote}"
        elif fmt == "mediawiki":
            return "<blockquote>\n" + render_blocks(node.children, fmt) + "\n</blockquote>"
        elif fmt == "bbcode":
            return "[quote]\n" + render_blocks(node.children, fmt) + "\n[/quote]"
        elif fmt == "org":
            return "#+BEGIN_QUOTE\n" + render_blocks(node.children, fmt) + "\n#+END_QUOTE"
        elif fmt == "slack":
            return prefix_lines(render_blocks(node.children, fmt), "> ")
        elif fmt == "jira":
            return "{quote}\n" + render_blocks(node.children, fmt) + "\n{quote}"
        elif fmt == "dokuwiki":
            return prefix_lines(render_blocks(node.children, fmt), "> ")
        elif fmt == "creole":
            return prefix_lines(render_blocks(node.children, fmt), "> ")
        elif fmt == "tiddlywiki":
            return "<<<\n" + render_blocks(node.children, fmt) + "\n<<<"
    if node.type == "list":
        if fmt == "html":
            tag = "ol" if node.ordered else "ul"
            items = []
            for item in node.items:
                body = render_inlines(item.children, fmt)
                if item.sublist:
                    body += "\n" + render(item.sublist, fmt)
                items.append("<li>" + body + "</li>")
            return f"<{tag}>\n" + "\n".join(items) + f"\n</{tag}>"
        elif fmt == "markdown":
            lines = []
            for number, item in enumerate(node.items, 1):
                marker = f"{number}. " if node.ordered else "- "
                lines.append(prefix_lines(render_inlines(item.children, fmt), marker, " " * len(marker)))
                if item.sublist:
                    lines.append(prefix_lines(render(item.sublist, fmt), " " * len(marker)))
            return "\n".join(lines)
        elif fmt == "plain":
            lines = []
            for number, item in enumerate(node.items, 1):
                marker = f"{number}) " if node.ordered else "* "
                lines.append(prefix_lines(render_inlines(item.children, fmt), marker, " " * len(marker)))
                if item.sublist:
                    lines.append(prefix_lines(render(item.sublist, fmt), " " * len(marker)))
            return "\n".join(lines)
        elif fmt == "latex":
            env = "enumerate" if node.ordered else "itemize"
            lines = ["\\begin{" + env + "}"]
            for item in node.items:
                lines.append(prefix_lines(render_inlines(item.children, fmt), "  \\item ", "  "))
                if item.sublist:
                    lines.append(prefix_lines(render(item.sublist, fmt), "  "))
            lines.append("\\end{" + env + "}")
            return "\n".join(lines)
        elif fmt == "mediawiki":
            marker = "#" if node.ordered else "*"
            lines = []
            for item in node.items:
                lines.append(marker + " " + render_inlines(item.children, fmt))
                if item.sublist:
                    lines.append(prefix_lines(render(item.sublist, fmt), marker))
            return "\n".join(lines)
        elif fmt == "bbcode":
            lines = ["[list=1]" if node.ordered else "[list]"]
            for item in node.items:
                lines.append("[*]" + render_inlines(item.children, fmt))
                if item.sublist:
                    lines.append(render(item.sublist, fmt))
            lines.append("[/list]")
            return "\n".join(lines)
        elif fmt == "org":
            lines = []
            for number, item in enumerate(node.items, 1):
                marker = f"{number}. " if node.ordered else "- "
                lines.append(prefix_lines(render_inlines(item.children, fmt), marker, " " * len(marker)))
                if item.sublist:
                    lines.append(prefix_lines(render(item.sublist, fmt), " " * len(marker)))
            return "\n".join(lines)
        elif fmt == "slack":
            lines = []
            for number, item in enumerate(node.items, 1):
                marker = f"{number}. " if node.ordered else "• "
                lines.append(prefix_lines(render_inlines(item.children, fmt), marker, "    "))
                if item.sublist:
                    lines.append(prefix_lines(render(item.sublist, fmt), "    "))
            return "\n".join(lines)
        elif fmt == "jira":
            marker = "#" if node.ordered else "*"
            lines = []
            for item in node.items:
                lines.append(marker + " " + render_inlines(item.children, fmt))
                if item.sublist:
                    lines.append(prefix_lines(render(item.sublist, fmt), marker))
            return "\n".join(lines)
        elif fmt == "dokuwiki":
            marker = "  - " if node.ordered else "  * "
            lines = []
            for item in node.items:
                lines.append(marker + render_inlines(item.children, fmt))
                if item.sublist:
                    lines.append(prefix_lines(render(item.sublist, fmt), "  "))
            return "\n".join(lines)
        elif fmt == "creole":
            marker = "#" if node.ordered else "*"
            lines = []
            for item in node.items:
                lines.append(marker + " " + render_inlines(item.children, fmt))
                if item.sublist:
                    lines.append(prefix_lines(render(item.sublist, fmt), marker))
            return "\n".join(lines)
        elif fmt == "tiddlywiki":
            marker = "#" if node.ordered else "*"
            lines = []
            for item in node.items:
                lines.append(marker + " " + render_inlines(item.children, fmt))
                if item.sublist:
                    lines.append(prefix_lines(render(item.sublist, fmt), marker))
            return "\n".join(lines)
    if node.type == "table":
        if fmt == "html":
            lines = ["<table>", "<tr>" + "".join("<th>" + render_inlines(cell, fmt) + "</th>" for cell in node.header) + "</tr>"]
            for row in node.rows:
                lines.append("<tr>" + "".join("<td>" + render_inlines(cell, fmt) + "</td>" for cell in row) + "</tr>")
            lines.append("</table>")
            return "\n".join(lines)
        elif fmt == "markdown":
            def row(cells):
                return "| " + " | ".join(render_inlines(cell, fmt) for cell in cells) + " |"
            lines = [row(node.header), "|" + "|".join(" --- " for _ in node.header) + "|"]
            lines += [row(cells) for cells in node.rows]
            return "\n".join(lines)
        elif fmt == "plain":
            rows = [[render_inlines(cell, fmt) for cell in node.header]] + [[render_inlines(cell, fmt) for cell in cells] for cells in node.rows]
            widths = [max(len(cells[i]) for cells in rows) for i in range(len(node.header))]
            def line(cells):
                return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()
            lines = [line(rows[0]), "-+-".join("-" * width for width in widths)]
            lines += [line(cells) for cells in rows[1:]]
            return "\n".join(lines)
        elif fmt == "latex":
            columns = "|" + "|".join("l" for _ in node.header) + "|"
            lines = ["\\begin{tabular}{" + columns + "}", "\\hline", " & ".join(render_inlines(cell, fmt) for cell in node.header) + " \\\\", "\\hline"]
            for cells in node.rows:
                lines.append(" & ".join(render_inlines(cell, fmt) for cell in cells) + " \\\\")
            lines += ["\\hline", "\\end{tabular}"]
            return "\n".join(lines)
        elif fmt == "mediawiki":
            lines = ['{| class="wikitable"', "! " + " !! ".join(render_inlines(cell, fmt) for cell in node.header)]
            for cells in node.rows:
                lines += ["|-", "| " + " || ".join(render_inlines(cell, fmt) for cell in cells)]
            lines.append("|}")
            return "\n".join(lines)
        elif fmt == "bbcode":
            lines = ["[table]", "[tr]" + "".join("[th]" + render_inlines(cell, fmt) + "[/th]" for cell in node.header) + "[/tr]"]
            for cells in node.rows:
                lines.append("[tr]" + "".join("[td]" + render_inlines(cell, fmt) + "[/td]" for cell in cells) + "[/tr]")
            lines.append("[/table]")
            return "\n".join(lines)
        elif fmt == "org":
            def row(cells):
                return "| " + " | ".join(render_inlines(cell, fmt) for cell in cells) + " |"
            lines = [row(node.header), "|" + "+".join("---" for _ in node.header) + "|"]
            lines += [row(cells) for cells in node.rows]
            return "\n".join(lines)
        elif fmt == "slack":
            rows = [[render_inlines(cell, fmt) for cell in node.header]] + [[render_inlines(cell, fmt) for cell in cells] for cells in node.rows]
            widths = [max(len(cells[i]) for cells in rows) for i in range(len(node.header))]
            lines = ["  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip() for cells in rows]
            return "```\n" + "\n".join(lines) + "\n```"
        elif fmt == "jira":
            lines = ["||" + "||".join(render_inlines(cell, fmt) for cell in node.header) + "||"]
            lines += ["|" + "|".join(render_inlines(cell, fmt) for cell in cells) + "|" for cells in node.rows]
            return "\n".join(lines)
        elif fmt == "dokuwiki":
            lines = ["^ " + " ^ ".join(render_inlines(cell, fmt) for cell in node.header) + " ^"]
            lines += ["| " + " | ".join(render_inlines(cell, fmt) for cell in cells) + " |" for cells in node.rows]
            return "\n".join(lines)
        elif fmt == "creole":
            lines = ["|=" + "|=".join(render_inlines(cell, fmt) for cell in node.header) + "|"]
            lines += ["|" + "|".join(render_inlines(cell, fmt) for cell in cells) + "|" for cells in node.rows]
            return "\n".join(lines)
        elif fmt == "tiddlywiki":
            lines = ["|!" + "|!".join(render_inlines(cell, fmt) for cell in node.header) + "|"]
            lines += ["|" + "|".join(render_inlines(cell, fmt) for cell in cells) + "|" for cells in node.rows]
            return "\n".join(lines)
    if node.type == "rule":
        if fmt == "html":
            return "<hr>"
        elif fmt == "markdown":
            return "---"
        elif fmt == "plain":
            return "* * *"
        elif fmt == "latex":
            return "\\noindent\\rule{\\linewidth}{0.4pt}"
        elif fmt == "mediawiki":
            return "----"
        elif fmt == "bbcode":
            return "[hr]"
        elif fmt == "org":
            return "-----"
        elif fmt == "slack":
            return "----------"
        elif fmt == "jira":
            return "----"
        elif fmt == "dokuwiki":
            return "----"
        elif fmt == "creole":
            return "----"
        elif fmt == "tiddlywiki":
            return "---"
    if node.type == "image":
        if fmt == "html":
            return '<img src="' + escape(node.src, fmt) + '" alt="' + escape(node.alt, fmt) + '">'
        elif fmt == "markdown":
            return "![" + escape(node.alt, fmt) + "](" + node.src.replace(" ", "%20").replace(")", "%29") + ")"
        elif fmt == "plain":
            return "[image: " + node.alt + "]"
        elif fmt == "latex":
            return "\\includegraphics{" + node.src + "}"
        elif fmt == "mediawiki":
            return "[[File:" + node.src + "|" + escape(node.alt, fmt) + "]]"
        elif fmt == "bbcode":
            return '[img alt="' + node.alt.replace('"', "'") + '"]' + node.src + "[/img]"
        elif fmt == "org":
            caption = "#+CAPTION: " + node.alt + "\n" if node.alt else ""
            return caption + "[[" + node.src + "]]"
        elif fmt == "slack":
            return "<" + node.src + "|" + (node.alt or node.src) + ">"
        elif fmt == "jira":
            return "!" + node.src + "|alt=" + node.alt + "!" if node.alt else "!" + node.src + "!"
        elif fmt == "dokuwiki":
            return "{{" + node.src + "|" + node.alt + "}}"
        elif fmt == "creole":
            return "{{" + node.src + "|" + node.alt + "}}"
        elif fmt == "tiddlywiki":
            return "[img[" + node.alt + "|" + node.src + "]]" if node.alt else "[img[" + node.src + "]]"
    if node.type == "figure":
        if fmt == "html":
            return ('<figure>\n<img src="' + escape(node.src, fmt) + '" alt="' + escape(node.alt, fmt) + '">\n<figcaption>' + render_inlines(node.caption, fmt)
                    + "</figcaption>\n</figure>")
        elif fmt == "markdown":
            return "![" + escape(node.alt, fmt) + "](" + node.src.replace(" ", "%20").replace(")", "%29") + ")\n\n*" + render_inlines(node.caption, fmt) + "*"
        elif fmt == "plain":
            return "[image: " + node.alt + "]\n" + render_inlines(node.caption, fmt)
        elif fmt == "latex":
            return "\\begin{figure}\n\\includegraphics{" + node.src + "}\n\\caption{" + render_inlines(node.caption, fmt) + "}\n\\end{figure}"
        elif fmt == "mediawiki":
            return "[[File:" + node.src + "|thumb|" + render_inlines(node.caption, fmt) + "]]"
        elif fmt == "bbcode":
            return '[img alt="' + node.alt.replace('"', "'") + '"]' + node.src + "[/img]\n[i]" + render_inlines(node.caption, fmt) + "[/i]"
        elif fmt == "org":
            return "#+CAPTION: " + render_inlines(node.caption, fmt) + "\n[[" + node.src + "]]"
        elif fmt == "slack":
            return "<" + node.src + "|" + (node.alt or node.src) + ">\n_" + render_inlines(node.caption, fmt) + "_"
        elif fmt == "jira":
            image = "!" + node.src + "|alt=" + node.alt + "!" if node.alt else "!" + node.src + "!"
            return image + "\n_" + render_inlines(node.caption, fmt) + "_"
        elif fmt == "dokuwiki":
            return "{{" + node.src + "|" + render_inlines(node.caption, fmt) + "}}"
        elif fmt == "creole":
            return "{{" + node.src + "|" + node.alt + "}}\n//" + render_inlines(node.caption, fmt) + "//"
        elif fmt == "tiddlywiki":
            image = "[img[" + node.alt + "|" + node.src + "]]" if node.alt else "[img[" + node.src + "]]"
            return image + "\n//" + render_inlines(node.caption, fmt) + "//"
    raise RenderError(f"unsupported node type: {node.type}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a JSON document to a markup format.")
    parser.add_argument("--to", required=True, help="output format")
    args = parser.parse_args(argv)
    try:
        if args.to not in FORMATS:
            raise RenderError(f"unknown format: {args.to}")
        output = render(build(json.load(sys.stdin)), args.to)
    except (RenderError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
