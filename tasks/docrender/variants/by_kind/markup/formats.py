"""Output formats: how each escapes text and separates blocks. Nodes render themselves (see nodes/)."""


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def escape_markdown(text: str) -> str:
    for ch in "\\`*_[]#|":
        text = text.replace(ch, "\\" + ch)
    return text

def escape_plain(text: str) -> str:
    return text

def escape_latex(text: str) -> str:
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

def escape_mediawiki(text: str) -> str:
    for ch, entity in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("[", "&#91;"), ("]", "&#93;")):
        text = text.replace(ch, entity)
    return text

def escape_bbcode(text: str) -> str:
    return "[noparse]" + text + "[/noparse]" if "[" in text else text

def escape_org(text: str) -> str:
    return text.replace("[[", "[\u200b[")

def escape_slack(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def escape_jira(text: str) -> str:
    for ch in "\\*_{}[]|":
        text = text.replace(ch, "\\" + ch)
    return text

def escape_dokuwiki(text: str) -> str:
    if any(ch in text for ch in "*/[]_'^|<>{}"):
        return "%%" + text + "%%"
    return text

def escape_creole(text: str) -> str:
    for ch in "~*/[]{}\\|=#":
        text = text.replace(ch, "~" + ch)
    return text

def escape_tiddlywiki(text: str) -> str:
    if any(ch in text for ch in "'/`[]{}<>^~_$|"):
        return '"""' + text + '"""'
    return text


ESCAPES = {
    "html": escape_html,
    "markdown": escape_markdown,
    "plain": escape_plain,
    "latex": escape_latex,
    "mediawiki": escape_mediawiki,
    "bbcode": escape_bbcode,
    "org": escape_org,
    "slack": escape_slack,
    "jira": escape_jira,
    "dokuwiki": escape_dokuwiki,
    "creole": escape_creole,
    "tiddlywiki": escape_tiddlywiki,
}

SEPARATORS = {
    "html": '\n',
    "markdown": '\n\n',
    "plain": '\n\n',
    "latex": '\n\n',
    "mediawiki": '\n\n',
    "bbcode": '\n\n',
    "org": '\n\n',
    "slack": '\n\n',
    "jira": '\n\n',
    "dokuwiki": '\n\n',
    "creole": '\n\n',
    "tiddlywiki": '\n\n',
}

FORMATS = list(ESCAPES)


def escape(text: str, fmt: str) -> str:
    return ESCAPES[fmt](text)


def inlines(children, fmt: str) -> str:
    return "".join(child.render(fmt) for child in children)


def blocks(children, fmt: str) -> str:
    return SEPARATORS[fmt].join(child.render(fmt) for child in children)
