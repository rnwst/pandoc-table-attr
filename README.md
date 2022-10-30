# pandoc-table-attr

A [pandoc](https://pandoc.org/index.html) [filter](https://pandoc.org/filters.html) that adds the capability of specifying [table attributes](https://hackage.haskell.org/package/pandoc-types-1.22.2.1/docs/Text-Pandoc-Definition.html#t:Attr) in [table captions](https://pandoc.org/MANUAL.html#tables) in [Pandoc's Markdown](https://pandoc.org/MANUAL.html#pandocs-markdown).


## How to use

Simply append attributes to table captions like so:
```
Table: Table caption. {#id .class key=val}

FirstCol   SecondCol
---------  ----------
FirstCell  SecondCell
```
The attributes specified in the table caption will then be added to pandoc's AST and used by pandoc's writers (the HTML writer utilises table attributes, but the author hasn't tested this with any of the other writers yet).

Table attributes must appear at the end of the table caption.


## Known limitations

The current implementation of pandoc-table-attr does not allow inline elements to be used in keyvalues if they would be parsed by pandoc as [inline formatting](https://pandoc.org/MANUAL.html#inline-formatting), [inline math](https://pandoc.org/MANUAL.html#math), [inline code blocks](https://pandoc.org/MANUAL.html#fenced-code-blocks) (Extension: `backtick_code_blocks`), [generic raw attributes](https://pandoc.org/MANUAL.html#generic-raw-attribute), [inline links](https://pandoc.org/MANUAL.html#inline-links), or [citations](https://pandoc.org/MANUAL.html#citation-syntax). Therefore, the following will not work:
```
Table: Table caption. {#id .class key="*val*"}
```
Pandoc will parse `*val*` as *emphasized text*, instead of literal asterisks. However, it is possible to use [backslash escapes](https://pandoc.org/MANUAL.html#backslash-escapes) as a workaround:
```
Table: Table caption. {#id .class key="\*val\*"}
```
The author hopes to remove this limitation soon.
