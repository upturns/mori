from interp import InPort, Procedure, read, evaluate, standard_env
from io import StringIO
import unittest


def i(s: str):
    env = standard_env()
    x = InPort(StringIO(s))
    i = read(x)
    return evaluate(i, env), env


class TestStringMethods(unittest.TestCase):

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
        val, env = i("(begin (define x 99) (define y 100) (+ x y))")
        self.assertEqual(val, 199)
        self.assertEqual(env.bindings['x'], 99)
        self.assertEqual(env.bindings['y'], 100)

    def test_let(self):
        val, env = i("(let ((x 99) (y 100)) (+ x y))")
        self.assertEqual(val, 199)
        self.assertFalse('x' in env.bindings)

    def test_letrec(self):
        x = i("""
            (letrec
                (
                    (even? (lambda (n) (cond (= n 0) #t (odd? (- n 1)))))
                    (odd? (lambda (n) (cond (= n 0) #f (even? (- n 1)))))
                )
                (even? 4)
            )
            """)
        self.assertTrue(x)

    def test_lambda(self):
        self.assertIsInstance(i("(lambda (x) (* 2 x))")[0], Procedure)
        self.assertEqual(i("((lambda (x) (* 2 x)) 3)")[0], 6)
        self.assertEqual(i("""
            (((lambda (x) (lambda (y) (+ x y)))
                99) 100)
        """)[0], 199)


if __name__ == '__main__':
    unittest.main()


