import unittest
from infi.django_rest_utils.pluck import collect_items_from_string_lists, pluck_result, traverse


class PluckTest(unittest.TestCase):
    def assertTraversalResultsIn(self, path, d, expectedResults):
        self.assertEquals(set(traverse(path, d)), set(expectedResults))

    def test_traversal(self):
        self.assertTraversalResultsIn('a', {'a': 1}, [('a', 1)])
        self.assertTraversalResultsIn('a.0', {'a': [1]}, [('a.0', 1)])
        self.assertTraversalResultsIn('a.2', {'a': [1]}, [('a.2', None)])
        self.assertTraversalResultsIn('a.k', {'a': [1]}, [('a.k', None)])
        self.assertTraversalResultsIn('z', {'a': 1}, [('z', None)])
        self.assertTraversalResultsIn('a.b', {'a': {'b': 2}}, [('a.b', 2)])
        self.assertTraversalResultsIn('*', [3, 4], [('0', 3), ('1', 4)])
        self.assertTraversalResultsIn('b.*', {'b': [3, 4]}, [('b.0', 3), ('b.1', 4)])
        self.assertTraversalResultsIn('y.*', {'b': [3, 4]}, [('y.*', None)])
        self.assertTraversalResultsIn('b.*.a', {'b': {'1': {'a': 5}, '2': {'a': 6}}}, [('b.1.a', 5), ('b.2.a', 6)])
        self.assertTraversalResultsIn('b.*.a', {'b': {'1': {'a': 5}, '2': {'a': 6}, '3': 7}}, [('b.1.a', 5), ('b.2.a', 6), ('b.3.a', None)])
        self.assertTraversalResultsIn('y.a', {'y': [3, 4]}, [('y.a', None)])
        self.assertTraversalResultsIn('a.0.', {'a': [1]}, [('a.0', 1)])

    def test_collect_items_from_string_lists(self):
        self.assertEquals(collect_items_from_string_lists(['a','b']), set(['a', 'b']))
        self.assertEquals(collect_items_from_string_lists(['a,b']), set(['a', 'b']))
        self.assertEquals(collect_items_from_string_lists(['a,b','c']), set(['a', 'b', 'c']))
        self.assertEquals(collect_items_from_string_lists(['a,b','a']), set(['a', 'b']))

    def test_pluck_results(self):
        self.assertEquals({'j':70, 'k': 90, 'v': None}, pluck_result({'t': 17, 'k': 90, 'j': 70}, ['j,k,v']))
        self.assertEquals({'a.b.c': 9, 'j':70},
            pluck_result({'a': {'b': {'c': 9, 'd': None}, 't': 17}, 'k': 10, 'j': 70}, ['a.b.c', 'j']))
