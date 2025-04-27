"""
Mori Scheme v0.1

Minimal implementation of the primitive special forms & procedures required to bootstrap Scheme.

Special Forms:
- quote
- lambda
- if
- set!
- define
- begin

The current implementation also includes `let` and `letrec`,
but these should be implemented in the MacroExpander eventually.

"""

import re
from typing import Callable, TypeGuard


class Symbol:
    name: str

    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return self.name

    def __eq__(self, other):
        if not isinstance(other, Symbol):
            return False
        return self.name == other.name


class Error:
    msg: str

    def __init__(self, msg: str):
        self.msg = msg

    def __repr__(self) -> str:
        return f"#<Error: {self.msg}>"


class Procedure:
    def __init__(self, parms, body, env) -> None:
        self.parms, self.body, self.env = parms, body, env

    def __repr__(self) -> str:
        return f"#<Procedure: {self.parms}.{self.body}>"


class Continuation:
    f: Callable

    def __init__(self, f, wind_stack):
        self.f = f
        self.wind_stack = list(wind_stack)


class InPort:
    "An input port. Retains a line of chars."

    tokenizer = r"""\s*(,@|[('`,)]|"(?:[\\].|[^\\"])*"|;.*|[^\s('"`,;)]*)(.*)"""

    def __init__(self, file):
        self.file = file
        self.line = ""

    def next_token(self) -> "Expr":
        "Return the next token, reading new text into line buffer if needed."
        while True:
            if self.line == "":
                self.line = self.file.readline()
            if self.line == "":
                return EOF_OBJECT
            m = re.match(InPort.tokenizer, self.line)
            if m:
                token, self.line = m.groups()
                if token != "" and not token.startswith(";"):
                    return token


class OutPort:
    "An output port"

    def __init__(self, file):
        self.file = file


ConsCell = tuple["Expr", "Expr"]

Expr = (
    int
    | float
    | str
    | Symbol
    | Procedure
    | Error
    | ConsCell
    | Callable[..., "Expr"]
    | InPort
    | OutPort
    | tuple[()]
)


class Env:
    outer: "Env | None"
    bindings: dict[str, Expr | Callable[..., Expr]]

    def __init__(self, params=(), args=(), outer=None):
        self.outer = outer
        param_names = []
        for param_expr in cons_list_to_python_list(params):
            if not isinstance(param_expr, Symbol):
                raise Exception("Invalid binding name!")
            param_names.append(param_expr.name)
        self.bindings = dict(zip(param_names, cons_list_to_python_list(args)))

    def find(self, var: Symbol) -> Expr | Callable[..., Expr]:
        if var.name in self.bindings:
            return self.bindings[var.name]
        elif self.outer:
            return self.outer.find(var)
        return Error(f"Variable '{var}' not found")

    def set(self, var: Symbol, val: Expr | Callable[..., Expr]):
        if var.name in self.bindings:
            self.bindings[var.name] = val
        elif self.outer:
            return self.outer.set(var, val)
        else:
            return Error(f"Cannot Set! Variable '{var}' not found")

    def __repr__(self):
        return str(self.bindings)


EOF_OBJECT = Symbol("#<eof-object>")


dynamic_wind_stack = []  # Stack of (before_expr, after_expr)


###########################################################
#                    HELPER UTILITIES                     #
###########################################################


def shared_prefix_length(stack1, stack2):
    i = 0
    while i < len(stack1) and i < len(stack2) and stack1[i] == stack2[i]:
        i += 1
    return i


def trampoline(f):
    while callable(f):
        f = f()
    return f


def cons_list_to_python_list(expr: Expr) -> list[Expr]:
    if isNull(expr):
        return []

    if not isPair(expr):
        raise Exception("Unable to convert to list:", expr)

    if len(expr) == 1:
        return expr

    if len(expr) != 2:
        raise Exception("Not a cons pair!")
    else:
        return [expr[0]] + cons_list_to_python_list(expr[1])


###########################################################
#                SPECIAL FORM EVALUATORS                  #
###########################################################


def evaluate_define(arg_exprs: ConsCell, env: Env, cont):
    header = car(arg_exprs)
    body = cadr(arg_exprs)

    if isinstance(header, Symbol):
        return lambda: evaluate(
            body,
            env,
            lambda val: (env.bindings.update({header.name: val}), lambda: cont(None))[
                1
            ],
        )

    if not isPair(header):
        raise Exception("Malformed definition (1)!")

    name = header[0]

    if not isinstance(name, Symbol):
        raise Exception("Malformed definition (2)!")

    params = header[1]
    p = Procedure(params, body, env)
    env.bindings[name.name] = p

    return lambda: cont(None)


def eval_sequence(exprs: ConsCell, env: Env, cont):
    """
    evaluates a sequence of expressions in order,
    discarding intermediate values and keeping the result of the last one
    """
    first, rest = exprs
    if isNull(rest):
        # Last expression: evaluate with original continuation
        return lambda: evaluate(first, env, cont)

    if not isPair(rest):
        raise Exception("Malformed list in eval sequence")

    # Otherwise: evaluate `first`, discard result, continue with rest
    return lambda: evaluate(
        first, env, lambda _ignored_value: lambda: eval_sequence(rest, env, cont)
    )


def evaluate_begin(exprs: ConsCell, env: Env, cont):
    return eval_sequence(exprs, env, cont)


def evaluate_if(args: ConsCell, env: Env, cont):
    cond_expr = car(args)
    conseq_expr = cadr(args)
    alt_expr = caddr(args)

    return lambda: evaluate(
        cond_expr,
        env,
        lambda cond: (lambda: evaluate(conseq_expr, env, cont))
        if cond
        else lambda: evaluate(alt_expr, env, cont),
    )


# cont should be a function that takes a list of exprs
def evaluate_args(arg_exprs: ConsCell, env: Env, cont):
    if len(arg_exprs) == 0:
        raise Exception("??")
        return lambda: cont([])

    first, rest = arg_exprs

    if isNull(rest):
        return lambda: evaluate(first, env, lambda val: lambda: cont((val, ())))

    if not isPair(rest):
        raise Exception("Malformed list in args evaluation")

    return lambda: evaluate(
        first,
        env,
        lambda val: evaluate_args(
            rest, env, lambda values: lambda: cont((val, values))
        ),
    )


def evaluate_let(arg_exprs: ConsCell, env: Env, cont):
    binding_exprs = car(arg_exprs)
    body_expr = cadr(arg_exprs)

    if not isPair(binding_exprs):
        raise Exception("Invalid bindings in let!")

    # binding_exprs is a linked list of pairs (k, v)
    # we want to map it into a linked list of just values
    binding_name_exprs = map_proper_list(binding_exprs, lambda b: car(b))
    binding_value_exprs = map_proper_list(binding_exprs, lambda b: cadr(b))

    def with_values(values):
        child_env = Env(binding_name_exprs, values, env)
        return lambda: evaluate(body_expr, child_env, cont)

    return evaluate_args(binding_value_exprs, env, with_values)


def evaluate_letrec(arg_exprs: ConsCell, env: Env, cont):
    binding_exprs = car(arg_exprs)
    body_expr = cadr(arg_exprs)

    if not isPair(binding_exprs):
        raise Exception("Invalid bindings in letrec!")

    names = []
    child_env = Env((), (), env)

    def map_letrec_binding(b):
        var_expr = b[0]
        names.append(var_expr.name)
        child_env.bindings[var_expr.name] = ()

    map_proper_list(binding_exprs, map_letrec_binding)
    val_exprs = map_proper_list(binding_exprs, lambda b: cadr(b))

    def with_values(values):
        child_env.bindings.update(dict(zip(names, cons_list_to_python_list(values))))
        return lambda: evaluate(body_expr, child_env, cont)

    return evaluate_args(val_exprs, child_env, with_values)


def evaluate_lambda(arg_exprs: ConsCell, env: Env, cont):
    param_exprs = car(arg_exprs)
    body_expr = cadr(arg_exprs)

    # If the lambda is a term (lambda (x) x),
    # it will still be parsed as `[lambda [x []] [x []]]`
    if not isPair(body_expr):
        return lambda: cont(Procedure(param_exprs, body_expr, env))

    return lambda: cont(Procedure(param_exprs, body_expr, env))


def eval_callcc(expr: ConsCell, env, k):
    f_expr = car(expr)

    if isPair(f_expr) and isNull(cdr(f_expr)):
        f_expr = car(f_expr)

    def apply_fn(f):
        # snapshot the dynamic-wind state
        cont = Continuation(k, dynamic_wind_stack[:])
        return evaluate(f.body, Env(f.parms, (cont, ()), env), k)

    return lambda: evaluate(f_expr, env, apply_fn)


def eval_set(arg_exprs: ConsCell, env: Env, cont):
    sym_expr = car(arg_exprs)
    val_expr = cadr(arg_exprs)
    if not isinstance(sym_expr, Symbol):
        raise Exception("Cannot use `set!` with a non-Symbol variable name")
    return lambda: evaluate(
        val_expr, env, lambda val: lambda: cont(env.set(sym_expr, val))
    )


def apply_continuation(func: Continuation, args, env: Env, from_stack):
    to_stack = func.wind_stack[:]
    prefix = shared_prefix_length(from_stack, to_stack)

    # Run all after thunks in from_stack that are not shared with to_stack (i.e., we're exiting them)
    # Run all before thunks in to_stack that are not shared with from_stack (i.e., we're entering them)
    def run_afters(i, k):
        if i < prefix:
            return run_befores(prefix, k)
        _, after = from_stack[i]
        return evaluate(after.body, env, lambda _: run_afters(i - 1, k))

    def run_befores(i, k):
        if i >= len(to_stack):
            # We are now in the destination context
            dynamic_wind_stack[:] = to_stack
            return k()
        before, _ = to_stack[i]
        return evaluate(before.body, env, lambda _: run_befores(i + 1, k))

    # Entry point: start unwinding and rewinding, then apply the continuation
    if len(args[1]) == 0:
        return run_afters(len(from_stack) - 1, lambda: func.f(args[0]))
    return run_afters(len(from_stack) - 1, lambda: func.f(args))


def eval_dynamic_wind(expr, env, cont):
    global dynamic_wind_stack
    before = car(expr)
    body = cadr(expr)
    after = caddr(expr)

    if not isinstance(before, Procedure):
        raise Exception("!")
    if not isinstance(body, Procedure):
        raise Exception("!")
    if not isinstance(after, Procedure):
        raise Exception("!")

    def run_before(_):
        dynamic_wind_stack.append((before, after))

        def run_body(result):
            return evaluate(
                after.body, env, lambda _: (dynamic_wind_stack.pop(), cont(result))[1]
            )

        return lambda: evaluate(body.body, env, run_body)

    return lambda: evaluate(before.body, env, run_before)


def evaluate(expr: Expr, env: Env, cont) -> Expr:
    if isPair(expr):
        fst = car(expr)
        rest = cdr(expr)

        if not isPair(rest):
            raise Exception("Malformed!")

        # print("Evaluating:", expr)
        # (special forms)
        # these functions work even if the global env is empty
        if fst == Symbol("define"):
            return evaluate_define(rest, env, cont)
        if fst == Symbol("begin"):
            return evaluate_begin(rest, env, cont)
        if fst == Symbol("if"):
            return evaluate_if(rest, env, cont)
        if fst == Symbol("let"):
            return evaluate_let(rest, env, cont)
        if fst == Symbol("letrec"):
            return evaluate_letrec(rest, env, cont)
        if fst == Symbol("lambda"):
            return evaluate_lambda(rest, env, cont)
        if fst == Symbol("set!"):
            return eval_set(rest, env, cont)
        if fst == Symbol("call/cc"):
            return eval_callcc(rest, env, cont)
        if fst == Symbol("quote"):
            if isNull(cdr(rest)):
                return lambda: cont(rest[0])
            return lambda: cont(rest)
        if fst == Symbol("dynamic-wind"):
            return lambda: evaluate_args(
                rest, env, lambda args: eval_dynamic_wind(args, env, cont)
            )

        def apply_procedure(proc: Procedure, args: Expr):
            return lambda: evaluate(proc.body, Env(proc.parms, args, proc.env), cont)

        def apply_primitive_procedure(builtin_func, args: Expr):
            return lambda: cont(builtin_func(args))

        def helper(func):
            if callable(func):
                # apply a builtin procedure
                return lambda: evaluate_args(
                    rest, env, lambda args: apply_primitive_procedure(func, args)
                )
            elif isinstance(func, Continuation):
                # apply a continuation
                return lambda: evaluate_args(
                    rest,
                    env,
                    lambda args: lambda: apply_continuation(
                        func, args, env, dynamic_wind_stack[:]
                    ),
                )
            elif isinstance(func, Procedure):
                # apply a user-defined procedure
                return lambda: evaluate_args(
                    rest, env, lambda args: apply_procedure(func, args)
                )
            else:
                raise Exception(
                    f"Unimplemented -- tried to apply a non procedure or builtin function: {expr}"
                )

        return evaluate(fst, env, helper)

    elif isinstance(expr, Symbol):
        return lambda: cont(env.find(expr))
    elif isinstance(expr, Procedure):
        return lambda: cont(expr)
    elif isinstance(expr, Error):
        raise Exception("Unimplemented")
    elif isinstance(expr, bool):
        return lambda: cont(expr)
    elif isinstance(expr, int):
        return lambda: cont(expr)
    elif isinstance(expr, float):
        return lambda: cont(expr)
    elif isinstance(expr, str):
        return lambda: cont(expr)
    elif isinstance(expr, InPort):
        return lambda: cont(expr)

    raise Exception("Unhandled")


###########################################################
#                        PARSER                           #
###########################################################


def readchar(inport):
    "Read the next character from an input port."
    if inport.line != "":
        ch, inport.line = inport.line[0], inport.line[1:]
        return ch
    else:
        return inport.file.read(1) or EOF_OBJECT


def build_proper_list(elements: list[Expr]) -> ConsCell | tuple[()]:
    "Build a proper list as nested cons cells."
    result: ConsCell | tuple[()] = ()
    for elem in reversed(elements):
        result = (elem, result)
    return result


def build_improper_list(elements, tail):
    "Build an improper list (dotted pair structure)."
    result = tail
    for elem in reversed(elements):
        result = (elem, result)
    return result


def read(inport) -> Expr:
    "Read a Scheme expression from an input port."

    def read_ahead(token) -> Expr:
        if "(" == token:
            L = []
            while True:
                token = inport.next_token()
                if token == ")":
                    return build_proper_list(L)
                elif token == ".":
                    # improper list detected
                    if not L:
                        raise SyntaxError("dot not after any elements")
                    cdr = read(inport)
                    token = inport.next_token()
                    if token != ")":
                        raise SyntaxError("expected ) to close dotted pair")
                    return build_improper_list(L, cdr)
                else:
                    L.append(read_ahead(token))
        elif ")" == token:
            raise SyntaxError("unexpected )")
        elif token in quotes:
            return (quotes[token], (read_ahead(inport.next_token()), ()))
        elif token is EOF_OBJECT:
            raise SyntaxError("unexpected EOF in list")
        else:
            return atom(token)

    # body of read:
    token1 = inport.next_token()
    return EOF_OBJECT if token1 is EOF_OBJECT else read_ahead(token1)


_quote = Symbol("quote")
# _quasiquote = Symbol("quote")
# _unquote = Symbol("unquote")
# _unquotesplicing = Symbol("unquote-splicing")
quotes = {
    "'": _quote,
    # "`":_quasiquote,
    # ",":_unquote,
    # ",@":_unquotesplicing
}


def atom(token) -> Expr:
    'Numbers become numbers; #t and #f are booleans; "..." string; otherwise Symbol.'
    if token == "#t":
        return True
    elif token == "#f":
        return False
    elif token[0] == '"':
        return token[1:-1]
    try:
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            #     try:
            #         return complex(token.replace('i', 'j', 1))
            #     except ValueError:
            #         return Symbol(token)
            return Symbol(token)


###########################################################
#                  BUILT-IN PROCEDURES                    #
###########################################################


def isPair(expr: Expr) -> TypeGuard[ConsCell]:
    return (isinstance(expr, tuple) or isinstance(expr, list)) and len(expr) == 2


def isNull(expr: Expr) -> TypeGuard[tuple[()]]:
    return (isinstance(expr, tuple) or isinstance(expr, list)) and len(expr) == 0


def isNumber(expr: Expr) -> TypeGuard[int | float]:
    return (isinstance(expr, int) or isinstance(expr, float)) and not isinstance(
        expr, bool
    )


def map_proper_list(exp: ConsCell, f) -> ConsCell:
    # todo: should probably use while loop instead of recursion
    if len(exp) == 0:
        return []
    if len(exp) != 2:
        raise Exception("Not proper list!")

    fst = exp[0]
    rest = exp[1]

    if isNull(rest):
        return (f(fst), ())
    elif not isPair(rest):
        raise Exception("Cannot use `map_proper_list` on improper list!")

    return (f(fst), map_proper_list(rest, f))


def reduce_proper_list(exp: ConsCell, f, accum) -> ConsCell:
    # todo: should probably use while loop instead of recursion
    if len(exp) == 0:
        return accum
    if len(exp) != 2:
        raise Exception("Not proper list!")
    fst = car(exp)
    rest = cdr(exp)

    if isNull(rest):
        return f(fst, accum)
    elif not isPair(rest):
        raise Exception("Cannot use `map_proper_list` on improper list!")

    return reduce_proper_list(rest, f, f(fst, accum))


def eq(args: ConsCell):
    fst = car(args)
    snd = cadr(args)
    return fst == snd


def add(args: ConsCell):
    # todo: verify 2+ args
    def _add_helper(curr, accum):
        return curr + accum

    return reduce_proper_list(args, _add_helper, 0)


def sub(args: ConsCell):
    # todo: verify 2+ args
    def _sub_helper(curr, accum):
        return accum - curr

    rest = cdr(args)
    if not isPair(rest):
        raise Exception("Malformed args for `sub`")
    return reduce_proper_list(rest, _sub_helper, args[0])


def mul(args: ConsCell):
    # todo: verify 2+ args
    def _mul_helper(curr, accum):
        return curr * accum

    return reduce_proper_list(args, _mul_helper, 1)


def div(args: ConsCell):
    # todo: verify 2+ args
    def _div_helper(curr, accum):
        return accum / curr

    rest = cdr(args)
    if not isPair(rest):
        raise Exception("Malformed args for `div`")
    return reduce_proper_list(rest, _div_helper, args[0])


def cons(args: ConsCell) -> ConsCell:
    return (car(args), cadr(args))


def car(args: ConsCell) -> Expr:
    return args[0]


def cdr(args: ConsCell) -> Expr:
    return args[1]


def cadr(args: ConsCell) -> Expr:
    if length(args) < 2:
        raise Exception("Cannot get CADR of list with < 2 items.")
    if not isPair(args[1]):
        raise Exception("Malformed list for CADR!")
    return args[1][0]


def caddr(args: ConsCell) -> Expr:
    if length(args) < 3:
        raise Exception("Cannot get CADDR of list with < 3 items.")
    if not isPair(args[1]):
        raise Exception("Malformed list for CADDR!")
    if not isPair(args[1][1]):
        raise Exception("Malformed list for CADDR!")
    return args[1][1][0]


# reverses a proper list
def reverse(lst):
    result = ()  # empty list
    while lst is not None:
        car = lst[0]
        if len(lst[1]) == 0:
            # this is the last cell
            result = (car, result)
            break
        else:
            cdr = lst[1]
            result = (car, result)
            lst = cdr
    return result


# gets the length of a cons list
def length(lst):
    result = 0
    while (isinstance(lst, list) or isinstance(lst, tuple)) and len(lst) > 0:
        result += 1
        lst = lst[1]
    if not (isinstance(lst, list) or isinstance(lst, tuple)):
        result += 1
    return result


def pretty_print(expr: ConsCell, indent=0, max_width=80):
    """Pretty-print a Scheme expression nicely aligned with indentation."""

    def pp(exp, current_indent):
        if isPair(exp):
            parts = []
            while isPair(exp):
                parts.append(pp(exp[0], current_indent + 1))
                exp = exp[1]
            if exp != []:  # improper list
                parts.append(".")
                parts.append(pp(exp, current_indent + 1))

            flat = "(" + " ".join(parts) + ")"
            if len(flat) + current_indent <= max_width:
                return flat
            else:
                inner_indent = current_indent + 2
                sep = "\n" + " " * inner_indent
                return "(" + sep + (sep).join(parts) + ")"
        else:
            return str(exp)

    formatted = pp(expr[0], indent)
    print(formatted)
    return ()


def lt(expr: ConsCell):
    fst = car(expr)
    snd = cadr(expr)
    if not isNumber(fst):
        raise Exception("Non numeric input for LT")
    if not isNumber(snd):
        raise Exception("Non numeric input for LT")
    return fst < snd


def gt(expr: ConsCell):
    fst = car(expr)
    snd = cadr(expr)
    if not isNumber(fst):
        raise Exception("Non numeric input for LT")
    if not isNumber(snd):
        raise Exception("Non numeric input for LT")
    return fst > snd


def standard_env():
    env = Env()
    env.bindings = {
        "+": add,
        "-": sub,
        "*": mul,
        "/": div,
        "<": lt,
        ">": gt,
        "not": lambda a: not car(a),
        # Equivalence Predicates
        "=": eq,
        "eq?": eq,
        "length": lambda args: length(car(args)),
        "reverse": lambda args: reverse(car(args)),
        "cons": cons,
        "car": car,
        "cdr": cdr,
        "cadr": cadr,
        "list": lambda args: args,
        "pair?": isPair,
        "null?": isNull,
        "atom?": lambda a: not isPair(a),
        "boolean?": lambda x: isinstance(car(x), bool),
        "number?": lambda args: isNumber(car(args)),
        "string?": lambda x: isinstance(car(x), str),
        "symbol?": lambda x: isinstance(car(x), Symbol),
        "eval": lambda expr: trampoline(evaluate(expr, env, lambda x: x)),
        # InPort Procedures
        "open-input-file": lambda fname: InPort(open(fname, "r")),
        "read": lambda inport: read(inport),
        # OutPort Procedures
        # todo: unimplemented
        # 'open-output-file': lambda fname: OutPort(open(fname, 'w')),
        # 'write': lambda obj, outport: lambda: outport.file.write(str(obj)),
        # Todo: if second arg is present, use it as OutPort
        "display": pretty_print,
        # 'newline': lambda _args: print(),
    }
    return env


if __name__ == "__main__":
    env = standard_env()
    with open("boot.scm", "r") as bootfile:
        expr = None
        while expr is not EOF_OBJECT:
            expr = read(InPort(bootfile))
            if expr is not EOF_OBJECT:
                result = trampoline(evaluate(expr, env, lambda x: x))
