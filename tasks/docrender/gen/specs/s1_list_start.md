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

{{EXAMPLE:list_start:continued:markdown}}

{{EXAMPLE:list_start:continued:latex}}
