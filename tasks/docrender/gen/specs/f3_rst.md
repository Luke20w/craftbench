# reStructuredText output

We're moving our developer docs to Sphinx, which reads reStructuredText. Please add it as an output
format: `--to rst`.

Blocks are separated by a blank line. In text, each of `` \ * ` _ | `` is preceded by a backslash. Below,
"…" is the node's children rendered as usual.

| node | reStructuredText |
|---|---|
| strong | `**…**` |
| emphasis | `*…*` |
| code | ` `` `, the value, ` `` ` |
| link | `` ` ``, the text, ` <URL>`, `` `_ `` |
| line_break | a single space |
| subscript | ``:sub:`…` `` |
| superscript | ``:sup:`…` `` |
| highlight | ``:mark:`…` `` |
| kbd | ``:kbd:`value` `` |
| math | ``:math:`value` `` |
| paragraph | its inlines |
| heading | the text, a newline, then the text's length in `=` (level 1), `-` (2), `~` (3) or `^` (4+) |
| code_block | `.. code-block:: LANGUAGE` (or `::` when there is no language), an empty line, then the code with every non-empty line indented by three spaces |
| quote | the blocks with every non-empty line indented by four spaces |
| list | one line per item: `- ` (unordered) or `N. ` (ordered, numbered from 1) and the item's inlines. A nested list goes after its item, surrounded by empty lines, with every non-empty line indented by the width of the item's marker. No trailing empty line at the end of the list |
| table | a simple table: columns padded to their widest cell and separated by two spaces (no trailing spaces); a border of `=` (one per column width, separated by two spaces) above the header, below the header and after the last row |
| rule | `----` |
| image | `.. image:: SRC`, and when alt isn't empty, a newline and `   :alt: ALT` |
| figure | `.. figure:: SRC`, the `:alt:` line as for images, an empty line, then three spaces and the caption |

{{EXAMPLE:rst:full:rst}}
