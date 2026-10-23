# AsciiDoc output

Part of the team writes in AsciiDoc and converts our output by hand every time. Please add AsciiDoc as an
output format: `--to asciidoc`.

Blocks are separated by a blank line. Text is written as is, except that text containing any of
``*_`#^~+[]`` is wrapped in `+++` … `+++`. Below, "…" is the node's children rendered as usual.

| node | AsciiDoc |
|---|---|
| strong | `*…*` |
| emphasis | `_…_` |
| code | `` `+ ``, the value as is, `` +` `` |
| link | the URL, then `[…]` |
| line_break | a space, `+` and a newline |
| subscript | `~…~` |
| superscript | `^…^` |
| highlight | `#…#` |
| kbd | `kbd:[value]` |
| math | `stem:[value]` |
| paragraph | its inlines |
| heading | `=` repeated (level + 1) times, at most 6, then a space and the text |
| code_block | a `[source,LANGUAGE]` line (only when there is a language), then `----`, the code and `----`, each on its own line |
| quote | `____`, the blocks and `____`, each on its own line |
| list | one line per item: `* ` (unordered) or `. ` (ordered) and the item's inlines. A nested list follows its item's line; on each of its lines that starts with `*` or `.`, that first character is doubled, so `* x` becomes `** x` |
| table | `\|===`; the header row as `\| a \| b`; an empty line; each row as `\| c \| d`; `\|===` (one per line) |
| rule | `'''` |
| image | `image::SRC[ALT]` |
| figure | `.` and the caption on its own line, then the image as above |

For example, this document:

```json
{"type": "document", "children": [{"type": "heading", "level": 1, "children": [{"type": "text", "value": "Release notes"}]}, {"type": "paragraph", "children": [{"type": "text", "value": "Version "}, {"type": "strong", "children": [{"type": "text", "value": "2.0"}]}, {"type": "text", "value": " is out. See "}, {"type": "link", "url": "https://example.com/notes", "children": [{"type": "text", "value": "the notes"}]}, {"type": "text", "value": "."}]}, {"type": "heading", "level": 2, "children": [{"type": "text", "value": "Changes"}]}, {"type": "list", "ordered": true, "items": [{"children": [{"type": "text", "value": "Faster "}, {"type": "code", "value": "render()"}], "sublist": null}, {"children": [{"type": "text", "value": "New formats"}], "sublist": {"type": "list", "ordered": false, "items": [{"children": [{"type": "text", "value": "org"}], "sublist": null}, {"children": [{"type": "text", "value": "jira"}], "sublist": null}]}}]}, {"type": "table", "header": [[{"type": "text", "value": "Name"}], [{"type": "emphasis", "children": [{"type": "text", "value": "Score"}]}], [{"type": "text", "value": "Note"}]], "rows": [[[{"type": "text", "value": "alice"}], [{"type": "text", "value": "10"}], [{"type": "code", "value": "ok"}]], [[{"type": "text", "value": "bob <b>"}], [{"type": "text", "value": "7"}], [{"type": "strong", "children": [{"type": "text", "value": "late"}]}, {"type": "text", "value": " again"}]], [[{"type": "text", "value": "carol"}], [{"type": "text", "value": "12"}], []]]}, {"type": "quote", "children": [{"type": "paragraph", "children": [{"type": "emphasis", "children": [{"type": "text", "value": "Thanks to everyone who helped."}]}]}]}, {"type": "code_block", "language": "sh", "code": "pip install docrender==2.0"}, {"type": "rule"}, {"type": "paragraph", "children": [{"type": "text", "value": "Done."}]}]}
```

renders with `--to asciidoc` as:

````
== Release notes

Version *2.0* is out. See https://example.com/notes[the notes].

=== Changes

. Faster `+render()+`
. New formats
** org
** jira

|===
| Name | _Score_ | Note

| alice | 10 | `+ok+`
| bob <b> | 7 | *late* again
| carol | 12 | 
|===

____
_Thanks to everyone who helped._
____

[source,sh]
----
pip install docrender==2.0
----

'''

Done.
````
