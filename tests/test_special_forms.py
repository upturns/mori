import unittest

from interp import Procedure, Symbol, pformat
from tests.test_utils import i


class TestEvalSpecialForms(unittest.TestCase):
    def test_eval_lambda(self):
        # basics
        self.assertIsInstance(i("(lambda () 99)")[0], Procedure)
        self.assertIsInstance(i("(lambda (x) x)")[0], Procedure)
        # multi-statement body
        self.assertIsInstance(
            i('(lambda () (display "Hello") (display " World"))')[0], Procedure
        )

    def test_lambda(self):
        self.assertIsInstance(i("(lambda (x) (* 2 x))")[0], Procedure)
        self.assertEqual(i("((lambda (x) x) 3)")[0], 3)
        self.assertEqual(i("((lambda (x) x) #t)")[0], True)
        self.assertEqual(i("((lambda (x) (* 2 x)) 3)")[0], 6)
        self.assertEqual(
            i("""
            (((lambda (x) (lambda (y) (+ x y)))
                99) 100)
        """)[0],
            199,
        )

        # 2 arg lambda
        self.assertEqual(i("((lambda (a b) (+ a b)) 2 3)")[0], 5)

    def test_variadic_lambda(self):
        self.assertEqual(i("((lambda (a . b) b) 1 2 3 4 5)")[0], (2, (3, (4, (5, ())))))
        self.assertEqual(i("((lambda (a b . c) c) 1 2 3 4 5)")[0], (3, (4, (5, ()))))
        self.assertEqual(i("((lambda (a . b) b) 1 2)")[0], (2, ()))

    def test_define(self):
        val, env = i("(define x 99)")
        self.assertEqual(val, ())
        self.assertEqual(env.bindings["x"], 99)

    def test_define_procedure(self):
        val, env = i("(define (dbl x) (* x 2))")
        self.assertEqual(val, ())
        self.assertIsInstance(env.bindings["dbl"], Procedure)
        self.assertEqual(i("(dbl 2)", env)[0], 4)

    def test_define_variadic_procedure(self):
        _val, env = i("(define (test x . y) y)")
        self.assertEqual(i("(test 1 2 3 4)", env)[0], (2, (3, (4, ()))))

        _val, env2 = i("(define (test2 x y . z) z)")
        self.assertEqual(i("(test2 1 2 3 4)", env2)[0], (3, (4, ())))

    def test_if(self):
        self.assertEqual(i("(if #t 1 2)")[0], 1)
        self.assertEqual(i("(if #f 1 2)")[0], 2)
        self.assertEqual(i("(if (= 1 1) 1 2)")[0], 1)
        self.assertEqual(i("(if (= 1 2) 1 2)")[0], 2)

    def test_begin(self):
        self.assertEqual(i("(begin)")[0], ())
        self.assertEqual(i("(begin 1)")[0], 1)
        self.assertEqual(i("(begin 1 2 3)")[0], 3)

        val, env = i("(begin (define x 99) (define y 100) (+ x y))")
        self.assertEqual(env.bindings["x"], 99)
        self.assertEqual(env.bindings["y"], 100)
        self.assertEqual(val, 199)

        self.assertEqual(
            i("""
            (begin
                (define f (lambda (x) (+ x 1)))
                (f 99)
                          )
            """)[0],
            100,
        )

        # Note the recurision is limited so that this should work without TCO implemented
        self.assertEqual(
            i("""
            (begin
                (define factorial (lambda (x acc)
                           (if (= x 0)
                              acc
                              (factorial (- x 1) (* x acc))
                           )
                           ))
                (factorial 5 1)
                          )
            """)[0],
            120,
        )

    def test_let(self):
        val, env = i("(let ((x 99) (y 100)) (+ x y))")
        self.assertEqual(val, 199)
        self.assertFalse("x" in env.bindings)

    def test_letrec(self):
        self.assertTrue(
            i("""
            (letrec
                (
                    (even? (lambda (n) (if (= n 0) #t (odd? (- n 1)))))
                    (odd? (lambda (n) (if (= n 0) #f (even? (- n 1)))))
                )
                (even? 8)
            )
            """)[0]
        )
        self.assertFalse(
            i("""
            (letrec
                (
                    (even? (lambda (n) (if (= n 0) #t (odd? (- n 1)))))
                    (odd? (lambda (n) (if (= n 0) #f (even? (- n 1)))))
                )
                (even? 9)
            )
            """)[0]
        )

    def test_quote(self):
        self.assertEqual(i("'99")[0], 99)
        self.assertEqual(i("'3.14")[0], 3.14)
        self.assertEqual(i("'#t")[0], True)
        self.assertEqual(i("'A")[0], Symbol("A"))
        self.assertEqual(i("'(1 2 3)")[0], (1, (2, (3, ()))))
        self.assertEqual(i("'((1 2) (3 4))")[0], ((1, (2, ())), ((3, (4, ())), ())))
        self.assertEqual(i("''a")[0], (Symbol("quote"), (Symbol("a"), ())))
        self.assertEqual(i("'(1 '2)")[0], (1, ((Symbol("quote"), (2, ())), ())))

    def test_quasiquote_unquote(self):
        # no unquote
        self.assertEqual(i("`99")[0], 99)
        self.assertEqual(i("`a")[0], Symbol("a"))
        self.assertEqual(i("`(1 2 3)")[0], (1, (2, (3, ()))))
        self.assertEqual(
            i("`(A B C)")[0], (Symbol("A"), (Symbol("B"), (Symbol("C"), ())))
        )

        # basic unquote
        self.assertEqual(i("`(A B ,3)")[0], (Symbol("A"), (Symbol("B"), (3, ()))))
        self.assertEqual(i("`(A B ,(+ 1 2))")[0], (Symbol("A"), (Symbol("B"), (3, ()))))
        self.assertEqual(
            pformat(i("(quasiquote ((unquote 'a) (unquote 'b)))")[0]), "(a b)"
        )

        # nested quasiquote
        self.assertEqual(i("``A")[0], (Symbol("quasiquote"), (Symbol("A"), ())))
        self.assertEqual(
            # i("`(1 2 `A)")[0], (1, (2, (Symbol("quasiquote"), (Symbol("A"), ())), ()))
            i("`(1 2 `A)")[0],
            (1, (2, ((Symbol("quasiquote"), (Symbol("A"), ())), ()))),
        )

        # nested unquote
        self.assertEqual(
            pformat(i("`(a `(b ,(+ 1 2) ,(foo ,(+ 1 3)) d))")[0]),
            "(a `(b ,(+ 1 2) ,(foo 4) d))",
        )

    def test_quasiquote_unquote_splice(self):
        # splice start
        self.assertEqual(i("`(,@(list 1 2) 3)")[0], (1, (2, (3, ()))))
        # splice end
        self.assertEqual(i("`(1 ,@(list 2 3))")[0], (1, (2, (3, ()))))
        # splice into middle
        self.assertEqual(i("`(1 ,@(list 2 3) 4)")[0], (1, (2, (3, (4, ())))))
        # whole expression
        self.assertEqual(i("`(,@(list 1 2 3))")[0], (1, (2, (3, ()))))
        # should fail:
        # self.assertEqual(i("`,@(list 1 2 3)")[0], (1, (2, (3, ()))))
        # dotted list splice
        self.assertEqual(i("`(1 ,@(list 2 3) . 4)")[0], (1, (2, (3, 4))))

    def test_set(self):
        self.assertEqual(
            i("""
            (begin
                (define x 0)
                (set! x 99)
                x
            )
            """)[0],
            99,
        )

        self.assertEqual(
            i("""
            (let (
                    (x 0))
                (begin (set! x 99)
                x)
            )
            """)[0],
            99,
        )

    def test_callcc(self):
        self.assertEqual(
            i("""
            (call/cc (lambda (k) 99))
        """)[0],
            99,
        )

        self.assertEqual(
            i("""
            (call/cc (lambda (k) (k 99)))
        """)[0],
            99,
        )

        self.assertEqual(
            i("""
            (call/cc (lambda (k) (begin (define t 0) (k 99) t)))
        """)[0],
            99,
        )

        self.assertEqual(
            i("""
            (+ 1 (call/cc (lambda (k) (+ 2 (k 3)))))
        """)[0],
            4,
        )

    def test_dynamic_wind(self):
        self.assertEqual(
            i("""
            (let
                ((path '()))
                (let ((add (lambda (x) (set! path (cons x path)))))
                    (begin
                        (add 'A)
                        (add 'B)
                        (add 'C)
                        path)))
            """)[0],
            (Symbol("C"), (Symbol("B"), (Symbol("A"), ()))),
        )
        self.assertEqual(
            i("""
            (let
                ((path '()))
                (let ((add (lambda (x) (set! path (cons x path)))))
                    (begin
                        (dynamic-wind
                            (lambda () (add 'A))
                            (lambda () (add 'B))
                            (lambda () (add 'C)))
                        path)))
            """)[0],
            (Symbol("C"), (Symbol("B"), (Symbol("A"), ()))),
        )

        # re-entering a continuation
        self.assertEqual(
            i("""
            (let ((path '())
                (c #f))
            (let ((add (lambda (s)
                        (set! path (cons s path)))))
                (begin
                    (dynamic-wind
                        (lambda () (add 'connect))
                        (lambda ()
                            (add (call/cc
                                (lambda (c0)
                                    (begin (set! c c0)
                                    'talk1)))))
                        (lambda () (add 'disconnect)))
                    (if (< (length path) 4)
                        (c 'talk2)
                        (reverse path))
                    )
                ))
            """)[0],
            (
                Symbol("connect"),
                (
                    Symbol("talk1"),
                    (
                        Symbol("disconnect"),
                        (
                            Symbol("connect"),
                            (Symbol("talk2"), (Symbol("disconnect"), ())),
                        ),
                    ),
                ),
            ),
        )

        # nested winding
        self.assertEqual(
            i("""
            (let
                ((path '()))
                (let ((add (lambda (x) (set! path (cons x path)))))
                    (begin
                        (dynamic-wind
                            (lambda () (add "enter-1"))
                            (lambda ()
                                (begin
                                    (dynamic-wind
                                        (lambda () (add "enter-2"))
                                        (lambda () (add "body-2"))
                                        (lambda () (add "exit-2")))
                                    (add "body-1")))
                            (lambda () (add "exit-1")))
                        (reverse path))))
            """)[0],
            (
                "enter-1",
                ("enter-2", ("body-2", ("exit-2", ("body-1", ("exit-1", ()))))),
            ),
        )
