"""Documents the hidden tests render."""


def t(value):
    return {"type": "text", "value": value}


def para(*children):
    return {"type": "paragraph", "children": list(children)}


def strong(*c):
    return {"type": "strong", "children": list(c)}


def em(*c):
    return {"type": "emphasis", "children": list(c)}


def code(v):
    return {"type": "code", "value": v}


def link(url, *c):
    return {"type": "link", "url": url, "children": list(c)}


BR = {"type": "line_break"}


def heading(level, *c):
    return {"type": "heading", "level": level, "children": list(c)}


def code_block(language, src):
    return {"type": "code_block", "language": language, "code": src}


def quote(*blocks):
    return {"type": "quote", "children": list(blocks)}


def item(*inlines, sublist=None):
    return {"children": list(inlines), "sublist": sublist}


def lst(ordered, *items):
    return {"type": "list", "ordered": ordered, "items": list(items)}


def table(header, rows):
    return {"type": "table", "header": header, "rows": rows}


RULE = {"type": "rule"}


def image(src, alt):
    return {"type": "image", "src": src, "alt": alt}


def sub(*c):
    return {"type": "subscript", "children": list(c)}


def sup(*c):
    return {"type": "superscript", "children": list(c)}


def hl(*c):
    return {"type": "highlight", "children": list(c)}


def kbd(v):
    return {"type": "kbd", "value": v}


def math(v):
    return {"type": "math", "value": v}


def figure(src, alt, *caption):
    return {"type": "figure", "src": src, "alt": alt, "caption": list(caption)}


def doc(*blocks):
    return {"type": "document", "children": list(blocks)}


NESTED_LIST = lst(False,
                  item(t("Fruit"), sublist=lst(True,
                                               item(t("apple")),
                                               item(strong(t("pear")), sublist=lst(False, item(t("green")), item(t("red")))))),
                  item(t("Vegetables"), BR, t("(seasonal)")),
                  item(t("Bread")))

TABLE = table([[t("Name")], [em(t("Score"))], [t("Note")]],
              [[[t("alice")], [t("10")], [code("ok")]],
               [[t("bob <b>")], [t("7")], [strong(t("late")), t(" again")]],
               [[t("carol")], [t("12")], []]])

BASE = {
    "inline": doc(para(t("Plain "), strong(t("bold")), t(", "), em(t("italic "), strong(t("both"))), t(", "),
                       code("x = 1"), t(", "), link("https://example.com/a b", t("a link")), t(" and"), BR,
                       t("a new line."))),
    "headings": doc(heading(1, t("Title")), heading(2, t("Section "), em(t("two"))), heading(3, t("Third")),
                    heading(4, t("Fourth level"))),
    "code": doc(code_block("python", "def f(x):\n    return x * 2\n\nprint(f(3))"),
                code_block("", "plain <text> & `ticks` ```"),
                para(t("Inline "), code("a`b"), t(" code."))),
    "quote": doc(quote(para(t("Quoted "), strong(t("words")), t(".")),
                       lst(False, item(t("one")), item(t("two"))),
                       quote(para(t("Nested quote."))))),
    "lists": doc(NESTED_LIST, lst(True, item(t("first")), item(t("second"), sublist=lst(True, item(t("inner")))))),
    "table": doc(TABLE),
    "media": doc(para(t("Above the line.")), RULE, image("img/cat 1.png", 'A "cat" [photo]'), image("x.png", "")),
    "extras": doc(para(t("H"), sub(t("2")), t("O and E = mc"), sup(t("2")), t(". "), hl(t("Important")), t(": press "),
                       kbd("Ctrl+C"), t(" then "), kbd("<Enter>"), t(". Area: "), math("\\pi r^2"), t(".")),
                  figure("img/chart.png", "Sales chart", t("Sales by "), em(t("quarter"))),
                  figure("raw.png", "", t("No alt text"))),
    "escaping": doc(para(t("Specials: a & b < c > \"q\" * _ ` [x] [[y]] # | \\ % $ { } ~ ^ ' / + - = @ !"))),
    "full": doc(heading(1, t("Release notes")),
                para(t("Version "), strong(t("2.0")), t(" is out. See "), link("https://example.com/notes", t("the notes")),
                     t(".")),
                heading(2, t("Changes")),
                lst(True, item(t("Faster "), code("render()")), item(t("New formats"), sublist=lst(False, item(t("org")),
                                                                                                  item(t("jira"))))),
                TABLE,
                quote(para(em(t("Thanks to everyone who helped.")))),
                code_block("sh", "pip install docrender==2.0"),
                RULE,
                para(t("Done."))),
}


def strike(*c):
    return {"type": "strikethrough", "children": list(c)}


def callout(variant, *blocks):
    return {"type": "callout", "variant": variant, "children": list(blocks)}


def dl(*items):
    return {"type": "definition_list", "items": [{"term": term, "definition": definition} for term, definition in items]}


CHANGE_DOCS = {
    "strikethrough": {
        "simple": doc(para(t("Price: "), strike(t("$10")), t(" $8"))),
        "nested": doc(para(strike(t("old "), strong(t("bold")), t(" text")), t(" and "), em(strike(t("gone"))))),
        "in_blocks": doc(heading(2, strike(t("Draft")), t(" Final")),
                         lst(False, item(strike(t("done"))), item(t("todo"))),
                         table([[t("Task")], [t("State")]], [[[t("ship")], [strike(t("open"))]]])),
    },
    "callout": {
        "note": doc(callout("note", para(t("Back up your data first.")))),
        "warning": doc(para(t("Before you start:")),
                       callout("warning", para(t("This "), strong(t("deletes")), t(" files.")),
                               lst(False, item(t("logs")), item(t("cache"))))),
        "tip": doc(callout("tip", para(t("Try this:")), code_block("sh", "make fast"),
                           quote(para(t("It worked for me."))))),
    },
    "definition_list": {
        "simple": doc(dl(([t("API")], [para(t("Application programming interface."))]),
                         ([t("CLI")], [para(t("Command-line interface."))]))),
        "rich": doc(heading(2, t("Glossary")),
                    dl(([code("render"), t(" "), em(t("verb"))],
                        [para(t("Turn a document into text.")), lst(True, item(t("parse")), item(t("emit")))]),
                       ([strong(t("node"))], [para(t("One element of the tree."))]))),
    },
}


def numbered_from(start, *items, ordered=True):
    return {**lst(ordered, *items), "start": start}


def cited(cite, *blocks):
    return {**quote(*blocks), "cite": cite}


CHANGE_DOCS.update({
    "list_start": {
        "continued": doc(lst(True, item(t("one")), item(t("two"))), para(t("A note between steps.")),
                         numbered_from(3, item(t("three")), item(t("four"), sublist=lst(True, item(t("four a")))))),
        "nested": doc(numbered_from(9, item(t("intro"), sublist=numbered_from(5, item(t("step five")), item(t("step six")))),
                                    ordered=False)),
        "explicit_one": doc(numbered_from(1, item(t("a")), item(t("b")))),
    },
    "quote_cite": {
        "simple": doc(cited([t("Edsger W. Dijkstra")], para(t("Simplicity is prerequisite for reliability.")))),
        "rich": doc(cited([strong(t("A happy user")), t(", "), em(t("2026"))],
                          para(t("It just works.")), lst(False, item(t("fast")), item(t("small"))))),
        "nested": doc(quote(para(t("Outer.")), cited([t("Someone")], para(t("Inner."))))),
    },
    "default_alt": {
        "image": doc({"type": "image", "src": "img/cat 1.png"}, {"type": "image", "src": "photo.jpg"}),
        "figure": doc({"type": "figure", "src": "charts/q3.png", "caption": [t("Third quarter")]}),
        "mixed": doc(image("a/b/keep.png", "Kept alt"), {"type": "image", "src": "plain.gif"}),
    },
})
