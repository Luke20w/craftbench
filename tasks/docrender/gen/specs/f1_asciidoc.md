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

{{EXAMPLE:asciidoc:full:asciidoc}}
