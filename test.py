#!/usr/bin/env python

"""Unit tests for pandoctableattributes."""

import unittest
import subprocess
import json
import re

from pandocfilters import Table

from pandoc_table_attr import stringify, despacify, destringify, \
                              dequotify, attr_regex, parse_caption, \
                              parse_attr, add_tab_attr


# Utility functions -----------------------------------------------------------

def pandoc(string, plain=False):
    """Convert string to pandoc AST representation."""
    cmd = ['pandoc', '-t', 'json']
    output = subprocess.check_output(cmd, input=string, text=True)
    blocks = json.loads(output)['blocks']
    if plain:
        if blocks[0]['t'] == 'Para':
            blocks[0]['t'] = 'Plain'
    return blocks


def mock_table(initial_caption, attr=None):
    """Create a mock table for pandoc."""
    # convert initial_caption to AST:
    caption_ast = \
        pandoc(initial_caption, plain=True) if initial_caption else []
    # See here for the Table data structure:
    # https://hackage.haskell.org/package/pandoc-types-1.22.2.1/docs/Text-Pandoc-Definition.html#t:Block
    short_caption = None
    caption  = [short_caption, caption_ast]
    table_head, table_body, table_foot = None, None, None
    return Table(attr, caption, table_head, table_body, table_foot)['c']


# Test class ------------------------------------------------------------------

class TestAddTabAttrs(unittest.TestCase):
    """Test the add_tab_attrs(...) function and its utilities."""

    # pylint: disable=missing-function-docstring

    def test_stringify(self):
        strings = ['a meaningless string',
                   '{#id .class key="val"} A caption.']
        for string in strings:
            str_ast = pandoc(string)[0]['c']
            stringified = stringify(str_ast)
            self.assertEqual([string], stringified)


    def test_despacify(self):
        string = 'This is a test string containing only words and spaces.'
        self.assertEqual(pandoc(string)[0]['c'], despacify(string))

        # Pandoc strips away leading and trailing spaces, but despacify
        # shouldn't.
        space = {'t': 'Space'}
        string = ' String with leading and trailing space. '
        expected = [space, *pandoc(string)[0]['c'], space]
        self.assertEqual(expected, despacify(string))


    def test_dequotify(self):
        strings = ['No quotes.',
                   '"quotes"',
                   'More "quotes".',
                   'Double "quotes \'inside\' quotes".',
                   "'Another \" quote inside' quotes.",
                   '"Quote \' inside" quotes.']
        for string in strings:
            # Pandoc will replace unmatched single and double quotes with
            # single and double primes (U+2032 and U+2033 respectively).
            ast_string = repr(pandoc(string)[0]['c']) \
                                     .replace('”', '"').replace('’', r'\'')
            # pylint: disable=eval-used
            self.assertEqual(eval(ast_string), dequotify(string))


    def test_stringify_and_destringify(self):
        string = ('{#id .class key="val \' val"} Caption '
                  'with @citation and *emphasized* test.')
        ast = pandoc(string)[0]['c']
        self.assertEqual(ast, destringify(stringify(ast)))


    def test_attr_regex(self):
        regex = attr_regex()
        captions = ['Caption. {#id}',
                    'Caption.{#id}',
                    'Caption. {.class1 .class2}',
                    'Caption{}. {#id}',
                    '{#id .class key=val}',
                    '{#id .class key = val}',
                    '{#id .class key1 = "val1" key2 = "val2"}',
                    '{key="val1\' val2"}']
        false_captions = ['Caption. {#id #id}',
                          'Caption. {#id, .class}',
                          'Caption. {#id .class',
                          'Caption. {#id .class klass}',
                          'Caption. {key=val"}',
                          'Caption. {key=val=val}',
                          'Caption. {#id .classkey=val}',
                          'Caption. {#id .class key= val1 val2}']
        for caption in captions:
            self.assertTrue(re.search(regex, caption))
        for caption in false_captions:
            self.assertFalse(re.search(regex, caption))


    def test_parse_caption(self):
        initial_caption = 'Caption. {#id .class key="val"}'
        caption, attr_str = parse_caption(mock_table(initial_caption))
        self.assertEqual(caption, pandoc('Caption.', plain=True)[0]['c'])
        self.assertEqual(attr_str, '#id .class key="val"')

        initial_caption = 'Caption.'
        caption, attr_str = parse_caption(mock_table(initial_caption))
        self.assertEqual(caption, pandoc(initial_caption)[0]['c'])
        self.assertEqual(attr_str, None)

        initial_caption = '{#id .class key="val"}'
        caption, attr_str = parse_caption(mock_table(initial_caption))
        self.assertEqual(caption, None)
        self.assertEqual(attr_str, '#id .class key="val"')

        # Empty caption.
        initial_caption = None
        caption, attr_str = parse_caption(mock_table(initial_caption))
        self.assertEqual(caption, None)
        self.assertEqual(attr_str, None)


    def test_parse_attr(self):
        attrs = [ ('#id .class key=val',
                   ('id', ['class'], [['key','val']])),
                  ('#id',
                   ('id', [], [])),
                  ('.class1 .class2',
                   ('', ['class1', 'class2'], [])),
                  ('key1=val1 key2=val2',
                   ('', [], [['key1', 'val1'], ['key2', 'val2']])),
                  ('key="val"',
                   ('', [], [['key', 'val']])),
                  ('key=val key=val',
                   ('', [], [['key', 'val']])) ]

        for attr, (ident, classes, keyvals) in attrs:
            _ident, _classes, _keyvals = parse_attr(attr)
            self.assertEqual(ident, _ident)
            self.assertEqual(classes, _classes)
            self.assertEqual(keyvals, _keyvals)


    def test_add_tab_attrs(self):
        # No caption. Filter needs to leave table unmodified (return 'None').
        self.assertEqual(None,
                         add_tab_attr('Table', mock_table(None), None, None))

        # Caption without attribute string should leave table unmodified
        # (return 'None').
        caption = "Some caption."
        self.assertEqual(None,
                        add_tab_attr('Table', mock_table(caption), None, None))

        # Caption containing only attr string. Filter needs to return modified
        # table.
        caption = '{#id}'
        self.assertEqual( { 't': 'Table',
                            'c': mock_table(None, attr=['id', [], []]) },
                          add_tab_attr('Table',
                                             mock_table(caption), None, None) )

        caption = 'Some caption. {#id}'
        self.assertEqual( { 't': 'Table',
                            'c': mock_table('Some caption.',
                                                        attr=['id', [], []]) },
                          add_tab_attr('Table',
                                             mock_table(caption), None, None) )


if __name__ == "__main__":
    unittest.main()
