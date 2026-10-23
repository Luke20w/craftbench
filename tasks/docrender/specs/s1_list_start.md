# Numbered lists that continue

Our how-to pages often split a numbered procedure with a note or a screenshot, and then the second half of
the steps starts again at 1. Writers need a list to be able to carry on counting.

A `list` node may now have an optional `start` field, an integer of 1 or more (default 1). It only affects
ordered lists; unordered lists ignore it. Each list, including a nested one, has its own `start`.

- Formats that write the item numbers (markdown, plain, org, slack) number the items from `start`.
- html: the opening tag is `<ol start="N">` when `start` isn't 1.
- latex: when `start` isn't 1, the line `  \setcounter{enumi}{N-1}` (two-space indent, N-1 being `start`
  minus one) comes right after `\begin{enumerate}`.
- bbcode: the opening tag is `[list=N]`.
- The other formats don't write numbers, so their output doesn't change.

Documents without `start` render exactly as before.

For example, this document:

```json
{"type": "document", "children": [{"type": "list", "ordered": true, "items": [{"children": [{"type": "text", "value": "one"}], "sublist": null}, {"children": [{"type": "text", "value": "two"}], "sublist": null}]}, {"type": "paragraph", "children": [{"type": "text", "value": "A note between steps."}]}, {"type": "list", "ordered": true, "items": [{"children": [{"type": "text", "value": "three"}], "sublist": null}, {"children": [{"type": "text", "value": "four"}], "sublist": {"type": "list", "ordered": true, "items": [{"children": [{"type": "text", "value": "four a"}], "sublist": null}]}}], "start": 3}]}
```

renders with `--to markdown` as:

````
1. one
2. two

A note between steps.

3. three
4. four
   1. four a
````

For example, this document:

```json
{"type": "document", "children": [{"type": "list", "ordered": true, "items": [{"children": [{"type": "text", "value": "one"}], "sublist": null}, {"children": [{"type": "text", "value": "two"}], "sublist": null}]}, {"type": "paragraph", "children": [{"type": "text", "value": "A note between steps."}]}, {"type": "list", "ordered": true, "items": [{"children": [{"type": "text", "value": "three"}], "sublist": null}, {"children": [{"type": "text", "value": "four"}], "sublist": {"type": "list", "ordered": true, "items": [{"children": [{"type": "text", "value": "four a"}], "sublist": null}]}}], "start": 3}]}
```

renders with `--to latex` as:

````
\begin{enumerate}
  \item one
  \item two
\end{enumerate}

A note between steps.

\begin{enumerate}
  \setcounter{enumi}{2}
  \item three
  \item four
  \begin{enumerate}
    \item four a
  \end{enumerate}
\end{enumerate}
````
