from tests.test_utils import i
from interp import Error, Symbol
import unittest


class TestPrimitiveProcedures(unittest.TestCase):
    def test_null_pred(self):
        # 0 args fails
        self.assertEqual(i("(null?)")[0], Error("Contract error"))
        # 1 arg
        self.assertTrue(i("(null? '())")[0])
        self.assertFalse(i("(null? 1)")[0])
        self.assertFalse(i("(null? 1.0)")[0])
        self.assertFalse(i('(null? "Hello")')[0])
        self.assertFalse(i("(null? 'a)")[0])
        self.assertFalse(i("(null? #t)")[0])
        self.assertFalse(i("(null? #f)")[0])
        self.assertFalse(i("(null? '(1 2 3))")[0])
        # 2+ args fails
        self.assertEqual(i("(null? '() '() #f)")[0], Error("Contract error"))
        self.assertEqual(i("(null? #f #f '())")[0], Error("Contract error"))
        self.assertEqual(i("(null? '() '())")[0], Error("Contract error"))

    def test_number_pred(self):
        # 0 args fails
        self.assertEqual(i("(number?)")[0], Error("Contract error"))
        # 1 arg
        self.assertFalse(i("(number? '())")[0])
        self.assertTrue(i("(number? 1)")[0])
        self.assertTrue(i("(number? 1.0)")[0])
        self.assertTrue(i("(number? -1.0)")[0])
        self.assertTrue(i("(number? 3.14)")[0])
        self.assertFalse(i('(number? "Hello")')[0])
        self.assertFalse(i("(number? 'a)")[0])
        self.assertFalse(i("(number? #t)")[0])
        self.assertFalse(i("(number? #f)")[0])
        self.assertFalse(i("(number? '(1 2 3))")[0])
        # 2+ args fails
        self.assertEqual(i("(number? 1 2 #f)")[0], Error("Contract error"))
        self.assertEqual(i("(number? #f #f 3.14)")[0], Error("Contract error"))
        self.assertEqual(i("(number? 99 100)")[0], Error("Contract error"))

    def test_string_pred(self):
        # 0 args fails
        self.assertEqual(i("(string?)")[0], Error("Contract error"))
        # 1 arg
        self.assertFalse(i("(string? '())")[0])
        self.assertFalse(i("(string? 1)")[0])
        self.assertFalse(i("(string? 1.0)")[0])
        self.assertFalse(i("(string? -1.0)")[0])
        self.assertFalse(i("(string? 3.14)")[0])
        self.assertTrue(i('(string? "Hello")')[0])
        self.assertTrue(i('(string? "")')[0])
        self.assertTrue(i('(string? "Hello World")')[0])
        self.assertTrue(i('(string? "  ")')[0])
        self.assertFalse(i("(string? 'a)")[0])
        self.assertFalse(i("(string? #t)")[0])
        self.assertFalse(i("(string? #f)")[0])
        self.assertFalse(i("(string? '(1 2 3))")[0])
        # 2+ args fails
        self.assertEqual(i('(string? "A" "B" #f)')[0], Error("Contract error"))
        self.assertEqual(i('(string? #f #f "A")')[0], Error("Contract error"))
        self.assertEqual(i('(string? "A" "B")')[0], Error("Contract error"))

    def test_symbol_pred(self):
        # 0 args fails
        self.assertEqual(i("(symbol?)")[0], Error("Contract error"))
        # 1 arg
        self.assertFalse(i("(symbol? '())")[0])
        self.assertFalse(i("(symbol? 1)")[0])
        self.assertFalse(i("(symbol? 1.0)")[0])
        self.assertFalse(i("(symbol? -1.0)")[0])
        self.assertFalse(i("(symbol? 3.14)")[0])
        self.assertFalse(i('(symbol? "Hello")')[0])
        self.assertFalse(i('(symbol? "")')[0])
        self.assertTrue(i("(symbol? 'a)")[0])
        self.assertTrue(i("(symbol? 'A)")[0])
        self.assertTrue(i("(symbol? 'Hello-Symbols)")[0])
        self.assertFalse(i("(symbol? #t)")[0])
        self.assertFalse(i("(symbol? #f)")[0])
        self.assertFalse(i("(symbol? '(1 2 3))")[0])
        # 2+ args fails
        self.assertEqual(i("(symbol? 'A 'B #f)")[0], Error("Contract error"))
        self.assertEqual(i("(symbol? #f #t 'A)")[0], Error("Contract error"))
        self.assertEqual(i("(symbol? 'A 'B)")[0], Error("Contract error"))

    def test_pair_pred(self):
        # 0 args fails
        self.assertEqual(i("(pair?)")[0], Error("Contract error"))
        # 1 arg
        self.assertFalse(i("(pair? '())")[0])
        self.assertFalse(i("(pair? 1)")[0])
        self.assertFalse(i("(pair? 1.0)")[0])
        self.assertFalse(i("(pair? -1.0)")[0])
        self.assertFalse(i("(pair? 3.14)")[0])
        self.assertFalse(i('(pair? "Hello")')[0])
        self.assertFalse(i('(pair? "")')[0])
        self.assertFalse(i("(pair? 'a)")[0])
        self.assertFalse(i("(pair? 'Hello-Symbols)")[0])
        self.assertFalse(i("(pair? #t)")[0])
        self.assertFalse(i("(pair? #f)")[0])
        self.assertTrue(i("(pair? '(1 2 3))")[0])
        self.assertTrue(i("(pair? '(1))")[0])
        self.assertTrue(i("(pair? '(1 . 2))")[0])
        self.assertTrue(i("(pair? '(() . ()))")[0])
        self.assertTrue(i("(pair? '(() ()))")[0])
        # 2+ args fails
        self.assertEqual(i("(pair? '(1 2) '(3 4) #f)")[0], Error("Contract error"))
        self.assertEqual(i("(pair? #f #t '(1 2))")[0], Error("Contract error"))
        self.assertEqual(i("(pair? '(1 2) '(3 4))")[0], Error("Contract error"))

    def test_sum(self):
        # no args returns 0
        self.assertEqual(i("(+)")[0], 0)
        # 1 arg returns the arg
        self.assertEqual(i("(+ 1)")[0], 1)
        self.assertEqual(i("(+ 3.14)")[0], 3.14)
        # 2 args
        self.assertEqual(i("(+ 0 0)")[0], 0)
        self.assertEqual(i("(+ 0 0)")[0], 0)
        self.assertEqual(i("(+ 1 1)")[0], 2)
        self.assertEqual(i("(+ -10 10.0)")[0], 0)
        self.assertEqual(i("(+ 1 2 3)")[0], 6)

        self.assertEqual(i("(+ 1 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(+ 'a 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(+ #f 0)")[0], Error("Contract error"))
        self.assertEqual(i('(+ "A" 0)')[0], Error("Contract error"))
        self.assertEqual(i('(+ "A" "B")')[0], Error("Contract error"))
        self.assertEqual(i("(+ 1 '())")[0], Error("Contract error"))
        self.assertEqual(i("(+ 1 '(1))")[0], Error("Contract error"))
        self.assertEqual(i("(+ '() '())")[0], Error("Contract error"))

    def test_sub(self):
        # no args fails
        self.assertEqual(i("(-)")[0], Error("Contract error"))
        # 1 arg
        self.assertEqual(i("(- 1)")[0], -1)
        self.assertEqual(i("(- 3.14)")[0], -3.14)
        # 2 args
        self.assertEqual(i("(- 0 0)")[0], 0)
        self.assertEqual(i("(- 1 1)")[0], 0)
        self.assertEqual(i("(- -10 10.0)")[0], -20)
        self.assertEqual(i("(- 1 2 3)")[0], -4)

        self.assertEqual(i("(- 1 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(- 'a 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(- #f 0)")[0], Error("Contract error"))
        self.assertEqual(i('(- "A" 0)')[0], Error("Contract error"))
        self.assertEqual(i('(- "A" "B")')[0], Error("Contract error"))
        self.assertEqual(i("(- 1 '())")[0], Error("Contract error"))
        self.assertEqual(i("(- 1 '(1))")[0], Error("Contract error"))
        self.assertEqual(i("(- '() '())")[0], Error("Contract error"))

    def test_mul(self):
        # no args returns 1
        self.assertEqual(i("(*)")[0], 1)
        # 1 arg returns the arg
        self.assertEqual(i("(* 2)")[0], 2)
        self.assertEqual(i("(* 3.14)")[0], 3.14)
        # 2+ args
        self.assertEqual(i("(* 0 0)")[0], 0)
        self.assertEqual(i("(* 1 1)")[0], 1)
        self.assertEqual(i("(* 1 0)")[0], 0)
        self.assertEqual(i("(* -10 10.0)")[0], -100)
        self.assertEqual(i("(* 1 2 3)")[0], 6)
        self.assertEqual(i("(* 2 3 4 5)")[0], 120)

        self.assertEqual(i("(* 1 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(* 'a 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(* #f 0)")[0], Error("Contract error"))
        self.assertEqual(i('(* "A" 0)')[0], Error("Contract error"))
        self.assertEqual(i('(* "A" "B")')[0], Error("Contract error"))
        self.assertEqual(i("(* 1 '())")[0], Error("Contract error"))
        self.assertEqual(i("(* 1 '(1))")[0], Error("Contract error"))
        self.assertEqual(i("(* '() '())")[0], Error("Contract error"))

    def test_div(self):
        # fails with 0 args
        self.assertEqual(i("(/)")[0], Error("Contract error"))
        # 1 arg returns it's reciprocal
        self.assertEqual(i("(/ 1)")[0], 1)
        self.assertEqual(i("(/ 2)")[0], 1 / 2)
        self.assertEqual(i("(/ 3)")[0], 1 / 3)
        # 2+ args
        self.assertEqual(i("(/ 1 1)")[0], 1)
        self.assertEqual(i("(/ 0 10)")[0], 0)
        self.assertEqual(i("(/ -10 10.0)")[0], -1)
        self.assertEqual(i("(/ 10 2)")[0], 5)
        self.assertEqual(i("(/ 30 3 5)")[0], 2)

        # divide by 0 causes an error
        self.assertRaises(ZeroDivisionError, lambda: i("(/ 0 0)")[0])
        self.assertRaises(ZeroDivisionError, lambda: i("(/ 10 0)")[0])
        self.assertRaises(ZeroDivisionError, lambda: i("(/ 1 2 0)")[0])

        # wrong input types
        self.assertEqual(i("(/ 1 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(/ 'a 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(/ #f 0)")[0], Error("Contract error"))
        self.assertEqual(i('(/ "A" 0)')[0], Error("Contract error"))
        self.assertEqual(i('(/ "A" "B")')[0], Error("Contract error"))
        self.assertEqual(i("(/ 1 '())")[0], Error("Contract error"))
        self.assertEqual(i("(/ 1 '(1))")[0], Error("Contract error"))
        self.assertEqual(i("(/ '() '())")[0], Error("Contract error"))

    def test_lt(self):
        # fails with 0 args
        self.assertEqual(i("(<)")[0], Error("Contract error"))
        # basic 2 arg case
        self.assertTrue(i("(< 0 1)")[0])
        self.assertTrue(i("(< 1 99)")[0])
        self.assertTrue(i("(< 3 3.14)")[0])
        # equal numbers fails
        self.assertFalse(i("(< 0 0)")[0])
        self.assertFalse(i("(< 10 10)")[0])
        self.assertFalse(i("(< 3.14 3.14)")[0])
        # supports 1 arg
        self.assertTrue(i("(< 0)")[0])
        self.assertTrue(i("(< 3.14)")[0])
        # supports 2+ args
        self.assertTrue(i("(< 1 2 3)")[0])
        self.assertFalse(i("(< 1 3 2)")[0])

        self.assertEqual(i("(< 1 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(< 'a 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(< #f 0)")[0], Error("Contract error"))
        self.assertEqual(i('(< "A" 0)')[0], Error("Contract error"))
        self.assertEqual(i('(< "A" "B")')[0], Error("Contract error"))
        self.assertEqual(i("(< 1 '())")[0], Error("Contract error"))
        self.assertEqual(i("(< 1 '(1))")[0], Error("Contract error"))
        self.assertEqual(i("(< '() '())")[0], Error("Contract error"))
        self.assertEqual(i("(< 1 2 'a)")[0], Error("Contract error"))

        # ensure type error is thrown before any comparisons are made
        self.assertEqual(i("(< 2 1'a)")[0], Error("Contract error"))

    def test_gt(self):
        # fails with 0 args
        self.assertEqual(i("(>)")[0], Error("Contract error"))

        # basic 2 arg case
        self.assertTrue(i("(> 1 0)")[0])
        self.assertTrue(i("(> 99 1)")[0])
        self.assertTrue(i("(> 3.14 3)")[0])
        # equal numbers fails
        self.assertFalse(i("(> 0 0)")[0])
        self.assertFalse(i("(> 10 10)")[0])
        self.assertFalse(i("(> 3.14 3.14)")[0])
        # supports 1 arg
        self.assertTrue(i("(> 0)")[0])
        self.assertTrue(i("(> 3.14)")[0])
        # supports 2+ args
        self.assertTrue(i("(> 3 2 1)")[0])
        self.assertFalse(i("(> 2 3 1)")[0])

        self.assertEqual(i("(> 1 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(> 'a 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(> #f 0)")[0], Error("Contract error"))
        self.assertEqual(i('(> "A" 0)')[0], Error("Contract error"))
        self.assertEqual(i('(> "A" "B")')[0], Error("Contract error"))
        self.assertEqual(i("(> 1 '())")[0], Error("Contract error"))
        self.assertEqual(i("(> 1 '(1))")[0], Error("Contract error"))
        self.assertEqual(i("(> '() '())")[0], Error("Contract error"))

        # ensure type error is thrown before any comparisons are made
        self.assertEqual(i("(> 1 2 'a)")[0], Error("Contract error"))

    def test_not(self):
        # 0 args fails
        self.assertEqual(i("(not)")[0], Error("Contract error"))
        # 1 args works for booleans
        self.assertTrue(i("(not #f)")[0])
        self.assertFalse(i("(not #t)")[0])
        # 2+ args fails
        self.assertEqual(i("(not #t #t)")[0], Error("Contract error"))
        self.assertEqual(i("(not #f #f)")[0], Error("Contract error"))
        self.assertEqual(i("(not #t #f #t)")[0], Error("Contract error"))
        self.assertEqual(i("(not #t #f 'a)")[0], Error("Contract error"))
        # any non-bool input returns false
        self.assertFalse(i("(not 'a)")[0])
        self.assertFalse(i('(not "A")')[0])
        self.assertFalse(i("(not 0)")[0])
        self.assertFalse(i("(not 1)")[0])
        self.assertFalse(i("(not '())")[0])
        self.assertFalse(i("(not '(1 2 3))")[0])

    def test_eq(self):
        # Tests whether two objects are the same exact object in memory.
        # 0 args fails
        self.assertEqual(i("(eq?)")[0], Error("Contract error"))
        # 1 arg fails
        self.assertEqual(i("(eq? #t)")[0], Error("Contract error"))
        # 2 args works
        # positive cases
        self.assertTrue(i("(eq? #t #t)")[0])
        self.assertTrue(i("(eq? 1 1)")[0])
        self.assertTrue(i("(eq? 3.14 3.14)")[0])
        self.assertTrue(i("(eq? 'A 'A)")[0])
        self.assertTrue(i('(eq? "Hello" "Hello")')[0])
        # Null & Null returns true
        self.assertTrue(i("(eq? '() '())")[0])
        # negative cases
        self.assertFalse(i("(eq? #t #f)")[0])
        self.assertFalse(i("(eq? 1 0)")[0])
        self.assertFalse(i("(eq? 3.14 3.15)")[0])
        self.assertFalse(i("(eq? 'A 'B)")[0])
        self.assertFalse(i('(eq? "Hello" "Hello World")')[0])
        # int and float of same value returns false
        self.assertFalse(i("(eq? 1 1.0)")[0])
        # always false for non-null lists/pairs
        self.assertFalse(i("(eq? '(1) '(1))")[0])
        self.assertFalse(i("(eq? '(1 2 3) '(1 2 3))")[0])

        # 3+ args fails
        self.assertEqual(i("(eq? 1 1 1)")[0], Error("Contract error"))

    def test_eqv(self):
        # 0 args fails
        self.assertEqual(i("(eqv?)")[0], Error("Contract error"))
        # 1 arg fails
        self.assertEqual(i("(eqv? 1)")[0], Error("Contract error"))
        self.assertEqual(i("(eqv? #t)")[0], Error("Contract error"))
        # 2 args positive cases
        # Null & Null returns true
        self.assertTrue(i("(eqv? '() '())")[0])
        # negative cases
        self.assertFalse(i("(eqv? #t #f)")[0])
        self.assertFalse(i("(eqv? 1 0)")[0])
        self.assertFalse(i("(eqv? 3.14 3.15)")[0])
        self.assertFalse(i("(eqv? 'A 'B)")[0])
        self.assertFalse(i('(eqv? "Hello" "Hello World")')[0])
        # int and float of same value returns false
        self.assertFalse(i("(eqv? 1 1.0)")[0])
        # doesn't work for pairs
        self.assertFalse(i("(eqv? '(1) '(1))")[0])

    def test_length(self):
        # 0 args fails
        self.assertEqual(i("(length)")[0], Error("Contract error"))
        # works with 1 list
        self.assertEqual(i("(length '())")[0], 0)
        self.assertEqual(i("(length '(1))")[0], 1)
        self.assertEqual(i("(length '(1 2 3))")[0], 3)
        self.assertEqual(i("(length '(a b c))")[0], 3)
        self.assertEqual(i("(length '(() () ()))")[0], 3)
        # fails with non-list arg
        self.assertEqual(i("(length 1)")[0], Error("Contract error"))
        self.assertEqual(i("(length 'a)")[0], Error("Contract error"))
        self.assertEqual(i('(length "hello")')[0], Error("Contract error"))
        # 2+ args fails
        self.assertEqual(i("(length '() '())")[0], Error("Contract error"))
        self.assertEqual(i("(length '(1 2 3) '(1 2 3))")[0], Error("Contract error"))

    def test_cons(self):
        # 0 args fails
        self.assertEqual(i("(cons)")[0], Error("Contract error"))
        # 1 arg fails
        self.assertEqual(i("(cons 1)")[0], Error("Contract error"))
        self.assertEqual(i("(cons '())")[0], Error("Contract error"))
        # 2 args works
        self.assertEqual(i("(cons 1 2)")[0], (1, 2))
        self.assertEqual(i("(cons 'a 'b)")[0], (Symbol("a"), Symbol("b")))
        self.assertEqual(i("(cons 1 '())")[0], (1, ()))
        self.assertEqual(i("(cons '() 1)")[0], ((), 1))
        self.assertEqual(i("(cons 1 '(2 3))")[0], (1, (2, (3, ()))))
        self.assertEqual(i("(cons '(1 2) 3)")[0], ((1, (2, ())), 3))
        self.assertEqual(i("(cons '(1 2) '(3 4))")[0], ((1, (2, ())), (3, (4, ()))))
        # 3+ args fails
        self.assertEqual(i("(cons 1 2 3)")[0], Error("Contract error"))

    def test_car(self):
        # 0 args fails
        self.assertEqual(i("(car)")[0], Error("Contract error"))
        # 1 pair works
        self.assertEqual(i("(car '(1))")[0], 1)
        self.assertEqual(i("(car '(a . b))")[0], Symbol("a"))
        self.assertEqual(i("(car '(1 2 3))")[0], 1)
        self.assertEqual(i("(car '((1 2 3) 4))")[0], (1, (2, (3, ()))))
        self.assertEqual(i("(car '((1 2 3) . 4))")[0], (1, (2, (3, ()))))
        # null input fails
        self.assertEqual(i("(car '())")[0], Error("Contract error"))
        # 2+ args fails
        self.assertEqual(i("(car '(1 2) '(3 4))")[0], Error("Contract error"))
        self.assertEqual(i("(car 1 2)")[0], Error("Contract error"))

    def test_cdr(self):
        # 0 args fails
        self.assertEqual(i("(cdr)")[0], Error("Contract error"))
        # 1 pair works
        self.assertEqual(i("(cdr '(1))")[0], ())
        self.assertEqual(i("(cdr '(a . b))")[0], Symbol("b"))
        self.assertEqual(i("(cdr '(1 2 3))")[0], (2, (3, ())))
        self.assertEqual(i("(cdr '((1 2 3) 4))")[0], (4, ()))
        self.assertEqual(i("(cdr '((1 2 3) . 4))")[0], 4)
        # null input fails
        self.assertEqual(i("(cdr '())")[0], Error("Contract error"))
        # 2+ args fails
        self.assertEqual(i("(cdr '(1 2) '(3 4))")[0], Error("Contract error"))
        self.assertEqual(i("(cdr 1 2)")[0], Error("Contract error"))

    def test_append(self):
        # 0 args returns Null
        self.assertEqual(i("(append)")[0], ())
        # 1 arg just returns that arg
        self.assertEqual(i("(append 1)")[0], 1)
        self.assertEqual(i("(append #f)")[0], False)
        self.assertEqual(i("(append #t)")[0], True)
        self.assertEqual(i("(append 'a)")[0], Symbol("a"))
        # null args do nothing
        self.assertEqual(i("(append '() '())")[0], ())
        self.assertEqual(i("(append '() 1)")[0], 1)
        self.assertEqual(i("(append '() 'a)")[0], Symbol("a"))
        self.assertEqual(i("(append '() '() 1)")[0], 1)
        # null after non-null fails
        self.assertEqual(i("(append 1 '())")[0], Error("Contract error"))
        self.assertEqual(i("(append '() 1 '())")[0], Error("Contract error"))
        # list after non-list fails
        self.assertEqual(i("(append '(1 2) 3 '(4 5))")[0], Error("Contract error"))
        # positive cases
        self.assertEqual(i("(append '(1) 2)")[0], (1, 2))
        self.assertEqual(i("(append '(1 2) 3)")[0], (1, (2, 3)))
        self.assertEqual(i("(append '(1) '())")[0], (1, ()))
        self.assertEqual(i("(append '(1) '(2))")[0], (1, (2, ())))
        self.assertEqual(i("(append '(1 2) '(3 4))")[0], (1, (2, (3, (4, ())))))
        # multiple lists
        self.assertEqual(
            i("(append '(1 2) '(3 4) '(5 6))")[0], (1, (2, (3, (4, (5, (6, ()))))))
        )
        self.assertEqual(
            i("(append '(1 2) '(3 4) '(5 6) 7)")[0], (1, (2, (3, (4, (5, (6, 7))))))
        )

    def test_apply(self):
        # 0 args fails
        self.assertEqual(i("(apply)")[0], Error("Contract error"))
        # 1 arg fails
        self.assertEqual(i("(apply +)")[0], Error("Contract error"))
        self.assertEqual(i("(apply '())")[0], Error("Contract error"))

        self.assertEqual(i("(apply + '(1 2 3))")[0], 6)
        self.assertEqual(i("(apply * '(2 3 4))")[0], 24)
        self.assertEqual(i("(apply list '(1 2 3))")[0], (1, (2, (3, ()))))
        self.assertEqual(i("(apply cons '(1 (2 3))) ")[0], (1, (2, (3, ()))))
        # apply with variadic params
        self.assertEqual(
            i("(apply (lambda (x . args) args) '(1 2 3))) ")[0], (2, (3, ()))
        )
        # 2+ args fails
        self.assertEqual(i("(apply + '(1 2 3) '(2 3 4))")[0], Error("Contract error"))

    def test_numeric_eq_pred(self):
        # 0 args fails
        self.assertEqual(i("(=)")[0], Error("Contract error"))
        # 1 arg returns true
        self.assertTrue(i("(= 1)")[0])
        self.assertTrue(i("(= 0)")[0])
        self.assertTrue(i("(= 0.1)")[0])
        self.assertTrue(i("(= 3.14)")[0])
        # 2 arg positive cases
        self.assertTrue(i("(= 1 1)")[0])
        self.assertTrue(i("(= 0 0)")[0])
        self.assertTrue(i("(= -1 -1)")[0])
        self.assertTrue(i("(= 0.1 0.1)")[0])
        self.assertTrue(i("(= 3.14 3.14)")[0])
        # 3+ arg positive cases
        self.assertTrue(i("(= 1 1 1)")[0])
        self.assertTrue(i("(= 0 0 0)")[0])
        self.assertTrue(i("(= -1 -1 -1)")[0])
        self.assertTrue(i("(= 3.14 3.14 3.14 3.14)")[0])
        # 1 wrong type arg fails
        self.assertEqual(i("(= #f)")[0], Error("Contract error"))
        self.assertEqual(i("(= #t)")[0], Error("Contract error"))
        self.assertEqual(i("(= '())")[0], Error("Contract error"))
        self.assertEqual(i('(= "A")')[0], Error("Contract error"))
        # wrong type of many args fails
        self.assertEqual(i("(= #f #f)")[0], Error("Contract error"))
        self.assertEqual(i("(= 1 #f)")[0], Error("Contract error"))
        self.assertEqual(i("(= 1 1 #f)")[0], Error("Contract error"))
        self.assertEqual(i("(= 1 1 #t)")[0], Error("Contract error"))
        self.assertEqual(i("(= 1 #t 2)")[0], Error("Contract error"))

    def test_bool_eq_pred(self):
        # 0 args returns True
        self.assertTrue(i("(boolean=?)")[0])
        # 1 arg returns True
        self.assertTrue(i("(boolean=? #t)")[0])
        self.assertTrue(i("(boolean=? #f)")[0])
        # 2 arg positive cases
        self.assertTrue(i("(boolean=? #t #t)")[0])
        self.assertTrue(i("(boolean=? #f #f)")[0])
        # 2 arg negative cases
        self.assertFalse(i("(boolean=? #f #t)")[0])
        self.assertFalse(i("(boolean=? #t #f)")[0])
        # 3+ arg positive cases
        self.assertTrue(i("(boolean=? #t #t #t)")[0])
        self.assertTrue(i("(boolean=? #t #t #t #t #t)")[0])
        self.assertTrue(i("(boolean=? #f #f #f)")[0])
        self.assertTrue(i("(boolean=? #f #f #f #f)")[0])
        # 3+ arg negative cases
        self.assertFalse(i("(boolean=? #f #t #t)")[0])
        self.assertFalse(i("(boolean=? #f #f #t)")[0])
        self.assertFalse(i("(boolean=? #f #f #f #f #t)")[0])
        # wrong type fails
        self.assertEqual(i("(boolean=? 0)")[0], Error("Contract error"))
        self.assertEqual(i("(boolean=? 1)")[0], Error("Contract error"))
        self.assertEqual(i("(boolean=? 'a)")[0], Error("Contract error"))
        self.assertEqual(i("(boolean=? #t #t 1)")[0], Error("Contract error"))

    def test_symbol_eq_pred(self):
        # 0 args returns True
        self.assertTrue(i("(symbol=?)")[0])
        # 1 arg returns True
        self.assertTrue(i("(symbol=? 'A)")[0])
        self.assertTrue(i("(symbol=? 'Hello-World)")[0])
        # 2 arg positive cases
        self.assertTrue(i("(symbol=? 'A 'A)")[0])
        self.assertTrue(i("(symbol=? 'Hello-World 'Hello-World)")[0])
        # 2 arg negative cases
        self.assertFalse(i("(symbol=? 'A 'B)")[0])
        self.assertFalse(i("(symbol=? 'Hello-World 'Hello-Moon)")[0])
        # 3+ arg positive cases
        self.assertTrue(i("(symbol=? 'A 'A 'A)")[0])
        self.assertTrue(i("(symbol=? 'A 'A 'A 'A)")[0])
        self.assertTrue(i("(symbol=? 'Hello-World 'Hello-World 'Hello-World)")[0])
        # 3+ arg negative cases
        self.assertFalse(i("(symbol=? 'A 'B 'B)")[0])
        self.assertFalse(i("(symbol=? 'B 'B 'A)")[0])
        self.assertFalse(i("(symbol=? 'A 'A 'A 'B)")[0])
        # wrong type fails
        self.assertEqual(i("(symbol=? 0)")[0], Error("Contract error"))
        self.assertEqual(i("(symbol=? 1)")[0], Error("Contract error"))
        self.assertEqual(i("(symbol=? #f)")[0], Error("Contract error"))
        self.assertEqual(i('(symbol=? "A")')[0], Error("Contract error"))
        self.assertEqual(i("""(symbol=? "A" 'A)""")[0], Error("Contract error"))
        self.assertEqual(i("(symbol=? #t #t 1)")[0], Error("Contract error"))

    def test_string_eq_pred(self):
        # 0 args returns True
        self.assertTrue(i("(string=?)")[0])
        # 1 arg returns True
        self.assertTrue(i('(string=? "")')[0])
        self.assertTrue(i('(string=? "A")')[0])
        self.assertTrue(i('(string=? "Hello World")')[0])
        # 2 arg positive cases
        self.assertTrue(i('(string=? "A" "A")')[0])
        self.assertTrue(i('(string=? "Hello World" "Hello World")')[0])
        # 2 arg negative cases
        self.assertFalse(i('(string=? "A" "B")')[0])
        self.assertFalse(i('(string=? "Hello World" "Hello Moon")')[0])
        self.assertFalse(i('(string=? "ABCDEFGHIJKL" "ABCDEFGHIJKLM")')[0])
        self.assertFalse(i('(string=? "ABCDEFGHIJKL" "ABCDEFGHIJK_")')[0])
        # 3+ arg positive cases
        self.assertTrue(i('(string=? "A" "A" "A")')[0])
        self.assertTrue(i('(string=? "A" "A" "A" "A")')[0])
        self.assertTrue(i('(string=? "Hello World" "Hello World" "Hello World")')[0])
        # 3+ arg negative cases
        self.assertFalse(i('(string=? "A" "B" "B")')[0])
        self.assertFalse(i('(string=? "B" "B" "A")')[0])
        self.assertFalse(i('(string=? "A" "A" "A" "B")')[0])
        # wrong type fails
        self.assertEqual(i("(string=? 0)")[0], Error("Contract error"))
        self.assertEqual(i("(string=? 1)")[0], Error("Contract error"))
        self.assertEqual(i("(string=? #f)")[0], Error("Contract error"))
        self.assertEqual(i("""(string=? "A" 'A)""")[0], Error("Contract error"))
        self.assertEqual(i("(string=? #t #t 1)")[0], Error("Contract error"))
        self.assertEqual(i("(string=? '())")[0], Error("Contract error"))

    def test_with_exception_handler(self):
        # thunk's val should be returned if no exception happens
        self.assertEqual(
            i("""
            (with-exception-handler (lambda (x) x) (lambda () 10))
        """)[0],
            10,
        )

        self.assertEqual(
            i("""
            (with-exception-handler (lambda (x) x) (lambda () (* 10 10)))
        """)[0],
            100,
        )

        # If a handler returns from `raise`, a new error is raised
        self.assertEqual(
            i("""
            (with-exception-handler (lambda (x) 123) (lambda () (+ "A" "A")))
        """)[0],
            (Error("Exception handler returned"), 123),
        )

        # Otherwise, it can escape using call/cc
        self.assertEqual(
            i("""
            (call/cc
              (lambda (k)
                (with-exception-handler
                    (lambda (err) (k 100))
                    (lambda () (NOT_A_VALID_FUNC)))))
            """)[0],
            100,
        )

    def test_raise(self):
        # basic
        self.assertEqual(i("""(raise 99)""")[0], 99)
        self.assertEqual(i("""(+ 1 (raise 99))""")[0], 99)

        # can escape using handler + call/cc
        self.assertEqual(
            i("""
            (call/cc
              (lambda (k)
                (with-exception-handler
                    (lambda (err) (k 'OK))
                    (lambda () (raise 'ERR)))))
            """)[0],
            Symbol("OK"),
        )

        # handled, but not escaped
        self.assertEqual(
            i("""
                (with-exception-handler
                    (lambda (x)
                        'OK)
                    (lambda ()
                        (raise 'ERR)))
            """)[0],
            (Error("Exception handler returned"), Symbol("OK")),
        )

    def test_raise_continuable(self):
        # handled, but not escaped
        self.assertEqual(
            i("""
                (with-exception-handler
                    (lambda (x)
                        'OK)
                    (lambda ()
                        (raise-continuable 'ERR)))
            """)[0],
            Symbol("OK"),
        )
