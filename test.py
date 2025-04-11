from interp import InPort, Procedure, read, evaluate, standard_env
from io import StringIO
import unittest


def i(s: str):
    env = standard_env()
    x = InPort(StringIO(s))
    i = read(x)
    return evaluate(i, env, lambda x: x), env


class TestStringMethods(unittest.TestCase):

    def test_atoms(self):
        self.assertEqual(i("#t")[0], True)
        self.assertEqual(i("#f")[0], False)
        self.assertEqual(i("99")[0], 99)
        self.assertEqual(i("3.14")[0], 3.14)

    def test_bool_ops(self):
        self.assertEqual(i("(= 1 1)")[0], True)
        self.assertEqual(i("(= 3.14 3.14)")[0], True)
        self.assertEqual(i("(= 0 0)")[0], True)
        self.assertEqual(i("(= #f #f)")[0], True)

        self.assertEqual(i("(= 0 1)")[0], False)
        self.assertEqual(i("(= #f #t)")[0], False)
        self.assertEqual(i("(= 3.1 3.14)")[0], False)

    def test_define(self):
        val, env = i("(define x 99)")
        self.assertEqual(val, None)
        self.assertEqual(env.bindings['x'], 99)

    def test_cond(self):
        self.assertEqual(i("(cond #t 1 2)")[0], 1)
        self.assertEqual(i("(cond #f 1 2)")[0], 2)
        self.assertEqual(i("(cond (= 1 1) 1 2)")[0], 1)
        self.assertEqual(i("(cond (= 1 2) 1 2)")[0], 2)

    def test_begin(self):
        self.assertEqual(i("(begin 1)")[0], 1)
        self.assertEqual(i("(begin 1 2 3)")[0], 3)

        val, env = i("(begin (define x 99) (define y 100) (+ x y))")
        self.assertEqual(env.bindings['x'], 99)
        self.assertEqual(env.bindings['y'], 100)
        self.assertEqual(val, 199)

    def test_lambda(self):
        self.assertIsInstance(i("(lambda (x) (* 2 x))")[0], Procedure)
        self.assertEqual(i("((lambda (x) (* 2 x)) 3)")[0], 6)
        self.assertEqual(i("""
            (((lambda (x) (lambda (y) (+ x y)))
                99) 100)
        """)[0], 199)

    def test_let(self):
        val, env = i("(let ((x 99) (y 100)) (+ x y))")
        self.assertEqual(val, 199)
        self.assertFalse('x' in env.bindings)

    def test_letrec(self):
        self.assertTrue(i("""
            (letrec
                (
                    (even? (lambda (n) (cond (= n 0) #t (odd? (- n 1)))))
                    (odd? (lambda (n) (cond (= n 0) #f (even? (- n 1)))))
                )
                (even? 8)
            )
            """)[0])
        self.assertFalse(i("""
            (letrec
                (
                    (even? (lambda (n) (cond (= n 0) #t (odd? (- n 1)))))
                    (odd? (lambda (n) (cond (= n 0) #f (even? (- n 1)))))
                )
                (even? 9)
            )
            """)[0])


if __name__ == '__main__':
    unittest.main()


