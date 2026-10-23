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

For example, this document:

```json
{"type": "document", "children": [{"type": "heading", "level": 1, "children": [{"type": "text", "value": "Release notes"}]}, {"type": "paragraph", "children": [{"type": "text", "value": "Version "}, {"type": "strong", "children": [{"type": "text", "value": "2.0"}]}, {"type": "text", "value": " is out. See "}, {"type": "link", "url": "https://example.com/notes", "children": [{"type": "text", "value": "the notes"}]}, {"type": "text", "value": "."}]}, {"type": "heading", "level": 2, "children": [{"type": "text", "value": "Changes"}]}, {"type": "list", "ordered": true, "items": [{"children": [{"type": "text", "value": "Faster "}, {"type": "code", "value": "render()"}], "sublist": null}, {"children": [{"type": "text", "value": "New formats"}], "sublist": {"type": "list", "ordered": false, "items": [{"children": [{"type": "text", "value": "org"}], "sublist": null}, {"children": [{"type": "text", "value": "jira"}], "sublist": null}]}}]}, {"type": "table", "header": [[{"type": "text", "value": "Name"}], [{"type": "emphasis", "children": [{"type": "text", "value": "Score"}]}], [{"type": "text", "value": "Note"}]], "rows": [[[{"type": "text", "value": "alice"}], [{"type": "text", "value": "10"}], [{"type": "code", "value": "ok"}]], [[{"type": "text", "value": "bob <b>"}], [{"type": "text", "value": "7"}], [{"type": "strong", "children": [{"type": "text", "value": "late"}]}, {"type": "text", "value": " again"}]], [[{"type": "text", "value": "carol"}], [{"type": "text", "value": "12"}], []]]}, {"type": "quote", "children": [{"type": "paragraph", "children": [{"type": "emphasis", "children": [{"type": "text", "value": "Thanks to everyone who helped."}]}]}]}, {"type": "code_block", "language": "sh", "code": "pip install docrender==2.0"}, {"type": "rule"}, {"type": "paragraph", "children": [{"type": "text", "value": "Done."}]}]}
```

renders with `--to rst` as:

````
Release notes
=============

Version **2.0** is out. See `the notes <https://example.com/notes>`_.

Changes
-------

1. Faster ``render()``
2. New formats

   - org
   - jira

=======  =======  ==============
Name     *Score*  Note
=======  =======  ==============
alice    10       ``ok``
bob <b>  7        **late** again
carol    12
=======  =======  ==============

    *Thanks to everyone who helped.*

.. code-block:: sh

   pip install docrender==2.0

----

Done.
````
