#!/usr/bin/env python

"""Add table attributes to pandoc's AST.

Table attributes can be specified as follows::

    Table: Caption {#id .class key=val}

    FirstCol  SecondCol
    --------- ----------

Todo:
----
- deal with single and double primes
- deal with other inline types that pandoc could create from attr string
- escaped quotation marks in vals?
- escaped underscores in vals?
"""

import re

from pandocfilters import toJSONFilter


def stringify(elts):
    """Turn pandoc AST element list into 'stringified' content.

    Utility function for add_tab_attr. See tests for behaviour.
    """
    almost_stringified = []
    for elt in elts:
        if elt['t'] == 'Str':
            almost_stringified.append(elt['c'])
        elif elt['t'] == 'Space':
            almost_stringified.append(' ')
        elif elt['t'] == 'Quoted':
            # The first content element will be either
            # {'t': 'SingleQuote'} or {'t': 'DoubleQuote'}.
            quote = "'" if elt['c'][0]['t'] == 'SingleQuote' else '"'
            almost_stringified  += [ quote, *stringify(elt['c'][1]), quote ]
        else:
            almost_stringified.append(elt)

    stringified = []
    for item in almost_stringified:
        if len(stringified) == 0:
            stringified.append(item)
        elif isinstance(item, str) and isinstance(stringified[-1], str):
            stringified[-1] += item
        else:
            stringified.append(item)

    return stringified


def despacify(string):
    """See tests for behaviour. Utility function for destringify."""
    if not string:
        return None

    # escape potential single quotes in w
    words = ["{'t': 'Str', 'c': '" + w.replace("'", r"\'") + "'}" if w else ''
                                                    for w in string.split(' ')]
    expr = ",{'t': 'Space'},".join(words)
    # remove potential leading and trailing commas due to spaces at start and
    # end of string
    expr = re.match(r'^,?(.*?),?$', expr).group(1)
    return eval('[' + expr + ']') # pylint: disable=eval-used


def dequotify(string):
    """See tests for behaviour. Utility function for destringify."""
    dequotified = []
    quotes = re.findall(r'".*?"|\'.*?\'', string)

    if quotes:
        escaped_quotes = [ re.escape(quote) for quote in quotes ]
        group_regex = r'^(.*?)(' + r')(.*?)('.join(escaped_quotes) + r')(.*?)$'
        split_string = [s for s in re.match(group_regex, string).groups() if s]

        for elt in split_string:
            if elt.startswith("'") or elt.startswith('"'):
                quote = 'SingleQuote' if elt.startswith("'") else 'DoubleQuote'
                naked_quote = elt[1:-1]
                dequotified.append(
                    {'t': 'Quoted',
                     'c': [{'t': quote}, dequotify(naked_quote)]} )
            else:
                dequotified += despacify(elt)

        return dequotified

    return despacify(string)


def destringify(stringified):
    """Turn 'stringified' content back into pandoc AST elements.

    Utility function for add_tab_attr. Quotes need to be taken care of first,
    then spaces. Otherwise a string like {#id .class key="foo bar"} will not
    be parsed properly.
    """
    destringified = []
    for elt in stringified:
        if isinstance(elt, str):
            destringified += dequotify(elt)
        else:
            destringified.append(elt)

    return destringified


def attr_regex(components=False):
    """Return regexes for attributes.

    Used for checking if attr is present at the end of a table caption and for
    extracting individual attributes.
    """
    # See https://www.w3.org/TR/html4/types.html
    ident = r'#(?P<id>[a-zA-Z][a-zA-Z0-9-_:\.]*)'

    # See
    # https://stackoverflow.com/questions/448981/which-characters-are-valid-in-css-class-names-selectors
    classes = r'\.(?P<class>[_a-zA-Z][_a-zA-Z0-9-]*)'

    # Keyvalues will be converted to HTML data-* attributes by pandoc, if key
    # is not a known HTML 5 attribute, 'width', or 'height':
    # https://pandoc.org/MANUAL.html#images
    # (under 'Extension: link_attributes').
    # Also see
    # https://stackoverflow.com/questions/19533402/naming-rules-for-html5-custom-data-attributedata
    keyvals   = (r'(?P<key>[_a-z][_a-z0-9-\.]*) *'
                 r'= *(?=(?P<v1>[^ "\'=\}\{]+)|"(?P<v2>.*?)"|\'(?P<v3>.*?)\')'
                 r'["\']?'
                 r'(?P<val>'
                 r'(?P=v1)(?!["\'])|(?<=")(?P=v2)(?=")|(?<=\')(?P=v3)(?=\'))'
                 r'["\']?')

    # An id should only appear once in attr_str. This is done using lookahead.
    # To use regular braces in f-strings, use double braces. Redefinition of
    # group name is not allowed, hence the need for the .replace().
    id_once = fr'(?!(?:.*{ ident.replace(r"P<id>", ":") }.*){{2,}})'

    attr = (fr'\{{{ id_once } *'
            fr'(?P<attr>(?:(?:{ ident }|{ classes }|{ keyvals })'
            fr'(?: +|(?=\}}$)))+)\}}$')

    def wrap(regex):
        return fr'(?: +|^){ regex }(?= +|$)'

    if components:
        return wrap(ident), wrap(classes), wrap(keyvals)

    return attr


def parse_caption(table):
    """Extract table caption from table and parse attributes if present.

    Utility function for add_tab_attr. Check for presence of
    '{#id .class key="val"}'. Return 'clean' caption without attributes as well
    as id, classes, and keyvals.
    """
    try:
        caption = table[1][1][0]['c']
    except IndexError:
        caption = None

    if not caption:
        return None, None

    caption = stringify(caption)
    match = re.search(attr_regex(), caption[-1]) \
                if isinstance(caption[-1], str) else None
    if match:
        attr_str = match.group('attr')
        caption_end = caption[-1][:match.start()]
        # strip away trailing spaces
        caption_end = re.match(r'^(.*?) *$', caption_end).group(1)
        clean_caption = destringify(caption[:-1] + [ caption_end ]) \
                                                       if caption_end else None
        return clean_caption, attr_str

    return destringify(caption), None


def parse_attr(attr_str):
    """Return AST representation of attr.

    Utility function for add_tab_attr. Returns parsed id, classes, and keyvals
    when given an attr string (the string inside curly braces).
    """
    ident_re, classes_re, keyvals_re = attr_regex(components=True)

    ident_match = re.search(ident_re, attr_str)
    ident = ident_match.group('id') if ident_match else ''

    # re.findall() returns a list of the *groups* matched whereas re.finditer()
    # returns an iterator yielding all the matches found.
    class_matches = re.finditer(classes_re, attr_str)
    classes = [ match.group('class') for match in class_matches ]

    keyval_matches = re.finditer(keyvals_re, attr_str)
    keyvals = { match.group('key') : match.group('val')
                                                  for match in keyval_matches }
    # convert dict to list of lists to match pandoc's AST representation
    keyvals = [ [ key, keyvals[key] ] for key in keyvals ]

    return ident, classes, keyvals


def add_tab_attr(key, value, _format, meta): # pylint: disable=unused-argument
    """Add attributes to table element in the AST if present in table caption.

    Add id, classes, and keyvals if the table caption contains
    {#id .class key="val"} at the end.
    """
    if key == 'Table':
        table = value
        caption, attr_str = parse_caption(table)
        if attr_str:
            ident, classes, keyvals = parse_attr(attr_str)
            # See here for the Table data structure:
            # https://hackage.haskell.org/package/pandoc-types-1.22.2.1/docs/Text-Pandoc-Definition.html#t:Block
            # The following could more conveniently be done using
            # pandocfilters' Table() function, but unfortunately this currently
            # takes an incorrect number of arguments.
            caption_elt = [{'t': 'Plain', 'c': caption}] if caption else []
            tab_content = [ [ident, classes, keyvals],
                            [None, caption_elt], *table[2:] ]
            return {'t': 'Table', 'c': tab_content}

    return None


if __name__ == "__main__":
    toJSONFilter(add_tab_attr)
