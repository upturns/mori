from tests.test_utils import i

# from interp import Error, Symbol
import unittest


class TestParser(unittest.TestCase):
    def test_atoms(self):
        self.assertEqual(i("#t")[0], True)
        self.assertEqual(i("#f")[0], False)
        self.assertEqual(i("99")[0], 99)
        self.assertEqual(i("3.14")[0], 3.14)

    def test_list(self):
        self.assertEqual(i("(list 1 2)")[0], (1, (2, ())))
        self.assertEqual(i("(list 1 2 3)")[0], (1, (2, (3, ()))))

    def test_dotted_list(self):
        self.assertEqual(i("'(1 . 2)")[0], (1, 2))
        self.assertEqual(i("'(1 2 . 3)")[0], (1, (2, 3)))
