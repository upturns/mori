import unittest

from tests.test_utils import i

# These imports appear unused, but are run by "unittest"
from tests.test_procedures import TestPrimitiveProcedures  # noqa: F401
from tests.test_special_forms import TestEvalSpecialForms  # noqa: F401
from tests.test_parser import TestParser  # noqa: F401


class TestTCO(unittest.TestCase):
    def test_tail_call_optimization(self):
        # These calls produce stack overflow errors if TCO is not implemented
        self.assertEqual(
            i("""
            (begin
                (define factorial (lambda (x acc)
                           (if (= x 0) acc
                                (factorial (- x 1) (* x acc))
                           )
                           ))
                (factorial 100 1)
                          )
        """)[0],
            93326215443944152681699238856266700490715968264381621468592963895217599993229915608941463976156518286253697920827223758251185210916864000000000000000000000000,
        )

        self.assertTrue(
            i("""
            (letrec
                (
                    (even? (lambda (n) (if (= n 0) #t (odd? (- n 1)))))
                    (odd? (lambda (n) (if (= n 0) #f (even? (- n 1)))))
                )
                (even? 1000)
            )
            """)[0]
        )


if __name__ == "__main__":
    unittest.main()
