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

{{EXAMPLE:textile:full:textile}}
