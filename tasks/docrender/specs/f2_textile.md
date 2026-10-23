# Textile output

Our partner's CMS only accepts Textile, so we copy-edit every page by hand before sending it. Please add
Textile as an output format: `--to textile`.

Blocks are separated by a blank line. Text is written as is, except that text containing any of
`*_+-^~@%!|` is wrapped in `==` … `==`. Below, "…" is the node's children rendered as usual.

| node | Textile |
|---|---|
| strong | `*…*` |
| emphasis | `_…_` |
| code | `@value@` |
| link | `"…":URL` |
| line_break | a newline |
| subscript | `~…~` |
| superscript | `^…^` |
| highlight | `%{background:yellow}…%` |
| kbd | `<kbd>value</kbd>` |
| math | `@value@` |
| paragraph | its inlines |
| heading | `hN. ` (N = level, at most 6) and the text |
| code_block | `bc(language-LANGUAGE).. ` (or `bc.. ` when there is no language) followed directly by the code |
| quote | `bq.. ` followed directly by the blocks |
| list | one line per item: `* ` (unordered) or `# ` (ordered) and the item's inlines. A nested list follows its item's line, with the parent's marker character added to the front of every one of its lines (`#* x` is an unordered item inside an ordered one) |
| table | the header row as `\|_. a\|_. b\|`, then each row as `\|c\|d\|`, one per line |
| rule | `---` |
| image | `!SRC(ALT)!`, or `!SRC!` when alt is empty |
| figure | the image as above, a newline, then `p(caption). ` and the caption |

For example, this document:

```json
{"type": "document", "children": [{"type": "heading", "level": 1, "children": [{"type": "text", "value": "Release notes"}]}, {"type": "paragraph", "children": [{"type": "text", "value": "Version "}, {"type": "strong", "children": [{"type": "text", "value": "2.0"}]}, {"type": "text", "value": " is out. See "}, {"type": "link", "url": "https://example.com/notes", "children": [{"type": "text", "value": "the notes"}]}, {"type": "text", "value": "."}]}, {"type": "heading", "level": 2, "children": [{"type": "text", "value": "Changes"}]}, {"type": "list", "ordered": true, "items": [{"children": [{"type": "text", "value": "Faster "}, {"type": "code", "value": "render()"}], "sublist": null}, {"children": [{"type": "text", "value": "New formats"}], "sublist": {"type": "list", "ordered": false, "items": [{"children": [{"type": "text", "value": "org"}], "sublist": null}, {"children": [{"type": "text", "value": "jira"}], "sublist": null}]}}]}, {"type": "table", "header": [[{"type": "text", "value": "Name"}], [{"type": "emphasis", "children": [{"type": "text", "value": "Score"}]}], [{"type": "text", "value": "Note"}]], "rows": [[[{"type": "text", "value": "alice"}], [{"type": "text", "value": "10"}], [{"type": "code", "value": "ok"}]], [[{"type": "text", "value": "bob <b>"}], [{"type": "text", "value": "7"}], [{"type": "strong", "children": [{"type": "text", "value": "late"}]}, {"type": "text", "value": " again"}]], [[{"type": "text", "value": "carol"}], [{"type": "text", "value": "12"}], []]]}, {"type": "quote", "children": [{"type": "paragraph", "children": [{"type": "emphasis", "children": [{"type": "text", "value": "Thanks to everyone who helped."}]}]}]}, {"type": "code_block", "language": "sh", "code": "pip install docrender==2.0"}, {"type": "rule"}, {"type": "paragraph", "children": [{"type": "text", "value": "Done."}]}]}
```

renders with `--to textile` as:

````
h1. Release notes

Version *2.0* is out. See "the notes":https://example.com/notes.

h2. Changes

# Faster @render()@
# New formats
#* org
#* jira

|_. Name|_. _Score_|_. Note|
|alice|10|@ok@|
|bob <b>|7|*late* again|
|carol|12||

bq.. _Thanks to everyone who helped._

bc(language-sh).. pip install docrender==2.0

---

Done.
````
