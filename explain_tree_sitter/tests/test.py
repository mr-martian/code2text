import tree_sitter_apertium as TSA
from ..translate import load_patterns, translate
import unittest

class TranslateTest(unittest.TestCase):
    language = TSA.CG
    text = 'LIST X = y ;\n'
    rules = []
    expected_output = '(source_file (list (LIST) (setname) (eq) (taglist (tag (ntag))) (semicolon)))'

    def test_output(self):
        patterns = load_patterns(self.rules, self.language)
        actual_output = translate(patterns, self.language, self.text)
        self.assertEqual(self.expected_output, actual_output)

class SimpleRule(TranslateTest):
    text = 'SELECT X ;'
    rules = [
        {'pattern': '(semicolon) @root', 'output': ''},
        {
            'pattern': '''
(
  (rule (ruletype) @type (rule_target) @target) @root
  (#match? @type "^SELECT$")
)
''',
            'output': 'Keep only readings matching {target}'
        },
        {
            'pattern': '''
(rule_target (inlineset (inlineset_single (setname) @name_text))) @root
''',
            'output': '{name_text}'
        },
    ]
    expected_output = '(source_file Keep only readings matching X)'

class ListRules(TranslateTest):
    text = 'SELECT X ; SELECT Y ;'
    rules = [
        {
            'pattern': '(source_file (_) @thing_list) @root',
            'output': [
                {
                    'lists': {
                        'thing_list': {
                            'join': '\n'
                        }
                    },
                    'output': '{thing_list}'
                }
            ]
        },
        {
            'pattern': '''
(
  (rule
    (ruletype) @type
    (rule_target (inlineset (inlineset_single (setname) @target_text)))
  ) @root
  (#match? @type "^SELECT$")
)
''',
            'output': 'Keep only readings matching {target_text}'
        },
    ]
    expected_output = 'Keep only readings matching X\nKeep only readings matching Y'

class ConditionalOutput(TranslateTest):
    text = 'SELECT X IF (1 Y) (2 Z) ;'
    rules = [
        {
            'pattern': '(source_file (_) @thing_list) @root',
            'output': [
                {
                    'lists': {
                        'thing_list': {
                            'join': '\n'
                        }
                    },
                    'output': '{thing_list}'
                }
            ]
        },
        {
            'pattern': '(inlineset (inlineset_single (setname) @name_text)) @root',
            'output': 'the set {name_text}'
        },
        {
            'pattern': '(contexttest (contextpos) @pos_text (_) @set) @root',
            'output': 'the cohort at position {pos_text} matches {set}'
        },
        {
            'pattern': '(rule ["(" ")"] @root)',
            'output': ''
        },
        {
            'pattern': '''
(
  (rule
    (ruletype) @type
    (rule_target (_) @target)
    [(contexttest) @test_list "(" ")"]*
  ) @root
  (#match? @type "^SELECT$")
)
''',
            'output': [
                {
                    'cond': [
                        {'has': 'test_list'}
                    ],
                    'output': 'If {test_list}, keep only readings matching {target}.',
                    'lists': {
                        'test_list': {
                            'join': ' and '
                        }
                    }
                },
                {
                    'output': 'Keep only readings matching {target}'
                }
            ]
        },
    ]
    expected_output = 'If the cohort at position 1 matches the set Y and the cohort at position 2 matches the set Z, keep only readings matching the set X.'
