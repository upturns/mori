"""
Mori Scheme v0.1

Minimal implementation of the primitive special forms & procedures required to bootstrap Scheme.

Special Forms:
- define
- sequence
- begin
- if
- let
- letrec
- lambda
- callcc
- set
- dynamic-wind
- quote
- quasiquote
- unquote
- unquote-splicing

The current implementation also includes `let` and `letrec`,
but these should be implemented in the MacroExpander eventually.

Primitive Procedures:
- Arithmetic: +, -, *, /, <, >
- Boolean: not, eq?, =
- Lists: cons, car, cdr, length, reverse, list, append
- Types: pair?, null?, atom?, boolean?, number?, string?, symbol?
- I/O: open-input-file, read, display, pretty-print, newline
- Misc: eval

"""

import re
from typing import Callable, TypeGuard, TypeVar, Union, cast
import logging
from functools import reduce


grey = "\x1b[90;20m"
yellow = "\x1b[33;20m"
red = "\x1b[31;20m"
bold_red = "\x1b[31;1m"
reset = "\x1b[0m"
format = (
    # "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    "[%(levelname)s] %(message)s"
)


class CustomFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


logger = logging.getLogger("APP")
logger.setLevel(logging.INFO)
logger.propagate = False
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

ch.setFormatter(CustomFormatter())
logger.addHandler(ch)


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


P = TypeVar("P", bound="Expr")
Q = TypeVar("Q", bound="Expr")


A = TypeVar("A", bound="Expr")
B = TypeVar("B", bound="Expr")
ConsCell = tuple[A, B]

Null = tuple[()]
L = TypeVar("L", "Expr", Null)
ProperList = Union[ConsCell[L, "ProperList[L]"], Null]


Atom = (
    int
    | float
    | str
    | Symbol
    | Procedure
    | Error
    | Callable[..., "Expr"]
    | InPort
    | OutPort
    | Null
)
Expr = Atom | ConsCell | ProperList

Thunk = Callable[[], "Thunk" | Expr]
InterpCont = Callable[[Expr], Expr | Thunk]


class Env:
    outer: "Env | None"
    bindings: dict[str, Expr | Callable[..., Expr]]

    def __init__(self, params=(), args=(), outer=None):
        self.outer = outer
        logger.debug(f"Instantiating new env with params: {params}")
        self.bindings = extract_bindings(params, args)

    def find(self, var: Symbol) -> Expr | Callable[..., Expr]:
        if var.name in self.bindings:
            return self.bindings[var.name]
        elif self.outer:
            return self.outer.find(var)
        return Error(f"Variable '{var}' not found")

    def set(self, var: Symbol, val: Expr | Callable[..., Expr]):
        if var.name in self.bindings:
            self.bindings[var.name] = val
            return val
        elif self.outer:
            return self.outer.set(var, val)
        else:
            raise Exception(f"Cannot Set! Variable '{var}' not found")

    def __repr__(self):
        return str(self.bindings)


EOF_OBJECT = Symbol("#<eof-object>")


WindStackItem = tuple[Expr, Expr]
dynamic_wind_stack: list[WindStackItem] = []  # Stack of (before_expr, after_expr)


###########################################################
#                    HELPER UTILITIES                     #
###########################################################


def shared_prefix_length(
    stack1: list[WindStackItem], stack2: list[WindStackItem]
) -> int:
    i = 0
    while i < len(stack1) and i < len(stack2) and stack1[i] == stack2[i]:
        i += 1
    return i


def trampoline(f: Thunk | Expr) -> Expr:
    while callable(f):
        exec_result = f()
        f = exec_result
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


def pformat(expr: Expr, indent: int = 0, max_width: int = 80) -> str:
    def collect_list_elements(exp: Expr):
        elems = []
        while isPair(exp):
            elems.append(exp[0])
            exp = exp[1]
        return tuple(elems), exp  # rest will be [] if proper

    def pp(exp: Expr, current_indent: int) -> str:
        # Handle pairs (lists or dotted pairs)
        if isPair(exp):
            fst = car(exp)
            rest = cdr(exp)
            # Handle quote-style syntax
            if fst == _quote:
                if not isPair(rest):
                    raise Exception("Error while formatting quote expr")
                return "'" + pp(car(rest), current_indent)
            if fst == _quasiquote:
                if not isPair(rest):
                    raise Exception("Error while formatting quasiquote expr")
                return "`" + pp(car(rest), current_indent)
            if fst == _unquote:
                if not isPair(rest):
                    raise Exception("Error while formatting unquote expr")
                return "," + pp(car(rest), current_indent)
            if fst == _unquotesplicing:
                if not isPair(rest):
                    raise Exception("Error while formatting unquote-splicing expr")
                return ",@" + pp(car(rest), current_indent)

            elems, tail = collect_list_elements(exp)
            parts = [pp(e, current_indent + 1) for e in elems]
            if not isNull(tail):
                parts.append(".")
                parts.append(pp(tail, current_indent + 1))

            flat = "(" + " ".join(parts) + ")"
            if len(flat) + current_indent <= max_width:
                return flat
            else:
                inner_indent = current_indent + 2
                sep = "\n" + " " * inner_indent
                return "(" + sep + (sep).join(parts) + ")"

        # Atoms
        return str(exp)

    formatted = pp(expr, indent)
    return formatted


def pretty_print(expr: Expr, indent: int = 0, max_width: int = 80) -> None:
    """Pretty-print a Scheme expression with indentation and shorthand syntax."""
    formatted = pformat(expr, indent, max_width)
    print(formatted)


def cons(p: P, q: Q) -> ConsCell[P, Q]:
    return (p, q)


def car(args: ConsCell[P, Q]) -> P:
    return args[0]


def cdr(args: ConsCell[P, Q]) -> Q:
    return args[1]


def cadr(args: ConsCell[Expr, ConsCell[P, Expr]]) -> P:
    return args[1][0]


def caddr(args: ConsCell[Expr, ConsCell[Expr, ConsCell[P, Expr]]]) -> P:
    return args[1][1][0]


# gets the length of a cons list
def length(lst: ProperList[Expr]) -> int:
    result = 0
    while isPair(lst):
        result += 1
        rest = cdr(lst)
        if not isPair(rest) and not isNull(rest):
            # todo: (length (1 . 2)) should raise an error
            result += 1
            break
        lst = cast(ProperList[Expr], rest)

    return result


# reverses a proper list
def reverse(lst: ProperList[P]) -> ProperList[P]:
    result: ProperList[P] = ()  # empty list
    while isNonNullProperList(lst):
        fst = car(lst)
        rest = cdr(lst)
        result = cast(ProperList[P], (fst, result))
        lst = rest

    return result


T = TypeVar("T")


def reduce_proper_list(exp: ProperList[P], f: Callable[[P, T], T], accum: T) -> T:
    # todo: should probably use while loop instead of recursion
    if isNonNullProperList(exp):
        fst = car(exp)
        rest = cdr(exp)

        if isNull(rest):
            return f(fst, accum)

        return reduce_proper_list(rest, f, f(fst, accum))
    return accum


def isPair(expr: Expr) -> TypeGuard[ConsCell[Expr, Expr]]:
    return (isinstance(expr, tuple) or isinstance(expr, list)) and len(expr) == 2


def isAtom(expr: Expr) -> TypeGuard[Atom]:
    return not (isinstance(expr, tuple) or isinstance(expr, list))


def isNull(expr: Expr) -> TypeGuard[Null]:
    logger.debug(f"Performing null check on: {expr}")
    return (isinstance(expr, tuple) or isinstance(expr, list)) and len(expr) == 0


def isNumber(expr: Expr) -> TypeGuard[int | float]:
    return (isinstance(expr, int) or isinstance(expr, float)) and not isinstance(
        expr, bool
    )


def match_type_contract(type_pattern: Expr, vals: Expr):
    if isNull(type_pattern):
        if not isNull(vals):
            return False
        return True
    if isNull(vals):
        if not isPair(type_pattern):
            return True
        return False

    if not isPair(type_pattern):
        type_pattern = cast(Callable[[Expr], bool], type_pattern)
        if isPair(vals):
            p = vals
            while not isNull(p):
                m = type_pattern(car(p))
                if not m:
                    return False
                p = cdr(p)
            return True
        m = type_pattern(vals)
        return m

    fst = car(type_pattern)
    rest = cdr(type_pattern)

    if not isinstance(fst, Callable):
        raise Exception("Invalid function in type pattern:", fst)

    if not isPair(vals):
        return False

    fst_val = car(vals)

    m = fst(fst_val)

    vals_rest = cdr(vals)
    if m:
        return match_type_contract(rest, vals_rest)
    return False


def extract_bindings(
    param_exprs: Expr, vals_exprs: Expr
) -> dict[str, Expr | Callable[..., Expr]]:
    if isNull(param_exprs) or isNull(vals_exprs):
        return {}

    if not isPair(param_exprs):
        if not isinstance(param_exprs, Symbol):
            raise Exception("Must be symbol in binding")
        return {param_exprs.name: vals_exprs}

    fst = car(param_exprs)
    rest = cdr(param_exprs)

    if not isPair(vals_exprs):
        return {}

    fst_val = car(vals_exprs)

    if not isinstance(fst, Symbol):
        raise Exception("Binding name must be a symbol")

    vals_rest = cdr(vals_exprs)

    return {fst.name: fst_val, **extract_bindings(rest, vals_rest)}


###########################################################
#                        PARSER                           #
###########################################################


def readchar(inport: InPort):
    "Read the next character from an input port."
    if inport.line != "":
        ch, inport.line = inport.line[0], inport.line[1:]
        return ch
    else:
        return inport.file.read(1) or EOF_OBJECT


def build_proper_list(elements: list[Expr]) -> ConsCell | Null:
    "Build a proper list as nested cons cells."
    result: ConsCell | Null = ()
    for elem in reversed(elements):
        result = (elem, result)
    return result


# Todo: this returns a ConsCell, but typing it requires some work.
def build_improper_list(elements: list[Expr], tail: Expr) -> Expr:
    "Build an improper list (dotted pair structure)."
    result = tail
    for elem in reversed(elements):
        result = (elem, result)
    return result


def read(inport: InPort) -> Expr:
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
_quasiquote = Symbol("quasiquote")
_unquote = Symbol("unquote")
_unquotesplicing = Symbol("unquote-splicing")
quotes = {"'": _quote, "`": _quasiquote, ",": _unquote, ",@": _unquotesplicing}


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
#                SPECIAL FORM EVALUATORS                  #
###########################################################


def eval_define(arg_exprs: ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    """
    (define <variable> <expression>)
    (define (<variable> <formals>) <body>)
    (define (<variable> . <formal>) <body>)
    """

    if isNonNullProperList(arg_exprs):
        header = car(arg_exprs)
        rest = cdr(arg_exprs)
        if not isPair(rest):
            raise Exception("Body is malformed in define")
        body = car(rest)
        logger.debug(f"Evaluating define. Header= {header}")

        if isinstance(header, Symbol):
            return lambda: evaluate(
                body,
                env,
                lambda val: (
                    env.bindings.update({header.name: val}),
                    lambda: cont(()),
                )[1],
            )

        if not isPair(header):
            raise Exception("Malformed definition (1)!")

        name = header[0]

        if not isinstance(name, Symbol):
            raise Exception("Malformed definition (2)!")

        params = header[1]
        p = Procedure(params, body, env)
        env.bindings[name.name] = p

        return lambda: cont(())
    raise Exception("No arguments passed to define")


def eval_sequence(exprs: ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    """
    evaluates a sequence of expressions in order,
    discarding intermediate values and keeping the result of the last one
    """
    if isNonNullProperList(exprs):
        first = car(exprs)
        rest = cdr(exprs)
        if isNull(rest):
            # Last expression: evaluate with original continuation
            return lambda: evaluate(first, env, cont)

        # Otherwise: evaluate `first`, discard result, continue with rest
        return lambda: evaluate(
            first, env, lambda _ignored_value: lambda: eval_sequence(rest, env, cont)
        )
    return lambda: cont(())


def eval_begin(exprs: ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    """
    syntax: (begin <expression or definition> …)

    syntax: (begin <expression1> <expression2> …)

    This form of begin can be used as an ordinary expression.
    The <expression>s are evaluated sequentially from left to right,
    and the values of the last <expression> are returned.
    """
    return eval_sequence(exprs, env, cont)


def eval_if(args: ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    """
    syntax: (if <test> <consequent> <alternate>)
    syntax: (if <test> <consequent>)
    First, <test> is evaluated. If it yields a true value, then <consequent> is evaluated and its values are returned.
    Otherwise <alternate> is evaluated and its values are returned.
    """

    m = match_type_contract(
        (lambda _: True, (lambda _: True, (lambda _: True, ()))), args
    )
    if not m:
        raise Exception(f"! {args}")

    args = cast(ConsCell[Expr, ConsCell[Expr, ConsCell[Expr, Null]]], args)

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
def eval_args(arg_exprs: ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    if isNonNullProperList(arg_exprs):
        first, rest = arg_exprs

        if isNonNullProperList(rest):
            return lambda: evaluate(
                first,
                env,
                lambda val: eval_args(
                    rest, env, lambda values: lambda: cont((val, values))
                ),
            )
        return lambda: evaluate(first, env, lambda val: lambda: cont((val, ())))

    return lambda: cont(())


def eval_let(arg_exprs: ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    """
    Syntax: (let <bindings> <body>)
    Bindings has form: ((<var_1> <init_1>) ...) where each <init> is an expression
    Body is a sequence of zero or more definitions
    """
    if isPair(arg_exprs):
        # # todo: this type contract
        m = match_type_contract((lambda _: True, (lambda _: True, ())), arg_exprs)
        if not m:
            raise Exception("!")

        arg_exprs = cast(
            ConsCell[ProperList[Expr], ConsCell[Expr, Null]],
            arg_exprs,
        )

        binding_exprs = car(arg_exprs)
        body_expr = cadr(arg_exprs)

        # binding_exprs is a linked list of pairs (k, v)
        # we want to map it into a linked list of just values
        binding_name_exprs = ()
        binding_value_exprs = ()
        b = binding_exprs
        while isNonNullProperList(b):
            binding = car(b)
            if not isPair(binding):
                raise Exception("Binding must be a pair")

            name_expr = car(binding)
            vals_expr = cdr(binding)

            if not isinstance(name_expr, Symbol):
                raise Exception("Binding name must be a symbol")

            if not isPair(vals_expr):
                raise Exception(
                    "Bindings should be properlists with form (<name> <val>)"
                )

            binding_name_exprs = (name_expr, binding_name_exprs)
            binding_value_exprs = (car(vals_expr), binding_value_exprs)
            b = cdr(b)

        def with_values(values):
            child_env = Env(binding_name_exprs, values, env)
            return lambda: evaluate(body_expr, child_env, cont)

        return eval_args(binding_value_exprs, env, with_values)
    raise Exception("No arguments passed to `let`")


def eval_letrec(arg_exprs: ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    """
    Syntax: (letrec <bindings> <body>)
    Bindings has form: ((<var_1> <init_1>) ...) where each <init> is an expression
    Body is a sequence of zero or more definitions
    """

    # # todo: this type contract
    m = match_type_contract((lambda _: True, (lambda _: True, ())), arg_exprs)
    if not m:
        raise Exception("!")

    arg_exprs = cast(
        ConsCell[ProperList[Expr], ConsCell[Expr, Null]],
        arg_exprs,
    )

    binding_exprs = car(arg_exprs)
    body_expr = cadr(arg_exprs)

    names = []
    child_env = Env((), (), env)

    binding_name_exprs = ()
    binding_value_exprs = ()
    b = binding_exprs
    while isPair(b):
        binding = car(b)
        if not isPair(binding):
            raise Exception("Binding must be a pair")

        name_expr = car(binding)
        vals_expr = cdr(binding)

        if not isinstance(name_expr, Symbol):
            raise Exception("Binding name must be a symbol")

        if not isPair(vals_expr):
            raise Exception("Bindings should be properlists with form (<name> <val>)")

        binding_name_exprs = (name_expr, binding_name_exprs)
        binding_value_exprs = (car(vals_expr), binding_value_exprs)

        child_env.bindings[name_expr.name] = ()
        names.append(name_expr.name)

        b = cdr(b)

    names.reverse()

    def with_values(values):
        child_env.bindings.update(dict(zip(names, cons_list_to_python_list(values))))
        return lambda: evaluate(body_expr, child_env, cont)

    return eval_args(binding_value_exprs, child_env, with_values)


def eval_lambda(arg_exprs: ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    """
    Syntax: (lambda <formals> <body>)
    Formals: is a "formals argument lists"
    """
    m = match_type_contract(
        (
            lambda x: isPair(x) or isNull(x) or isinstance(x, Symbol),
            (lambda _: True, ()),
        ),
        arg_exprs,
    )
    if not m:
        raise Exception("!")

    arg_exprs = cast(
        ConsCell[Symbol | ProperList[Expr] | Null, ConsCell[Expr, Null]], arg_exprs
    )

    param_exprs = car(arg_exprs)
    body_expr = cadr(arg_exprs)

    return lambda: cont(Procedure(param_exprs, body_expr, env))


def eval_set(arg_exprs: ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    """
    Syntax: (set! <variable> <expression>)
    """
    m = match_type_contract(
        (lambda x: isinstance(x, Symbol), (lambda _: True, ())), arg_exprs
    )
    if not m:
        raise Exception("!")

    arg_exprs = cast(ConsCell[Symbol, ConsCell[Expr, Null]], arg_exprs)

    sym_expr = car(arg_exprs)
    val_expr = cadr(arg_exprs)
    return lambda: evaluate(
        val_expr, env, lambda val: lambda: cont(env.set(sym_expr, val))
    )


def apply_continuation(
    func: Continuation,
    args: ProperList[Expr],
    env: Env,
    from_stack: list[WindStackItem],
) -> Thunk:
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
    if isNonNullProperList(args):
        if isNull(cdr(args)):
            return run_afters(len(from_stack) - 1, lambda: func.f(car(args)))
    return run_afters(len(from_stack) - 1, lambda: func.f(args))


def apply_procedure(proc: Procedure, args: Expr, cont: InterpCont) -> Thunk:
    logger.debug(f"Applying defined procedure {proc} to {args}")
    return lambda: evaluate(proc.body, Env(proc.parms, args, proc.env), cont)


def apply_primitive_procedure(
    builtin_func: Callable, args: Expr, env: Env, cont: InterpCont
) -> Thunk:
    logger.debug(f"Applying primitive procedure {builtin_func} to {args}")
    return lambda: builtin_func(args, env, cont)


def _expand_quasiquote(expr: Expr, env: Env, depth: int = 0) -> Expr:
    if isPair(expr):
        if car(expr) == _unquote:
            if depth == 0:
                unquote_args = cdr(expr)
                if not isPair(unquote_args):
                    raise Exception("Invalid args to unquote")
                return trampoline(evaluate(car(unquote_args), env, lambda x: x))
            return (
                Symbol("unquote"),
                _expand_quasiquote(expr[1], env, depth - 1),
            )
        elif car(expr) == _unquotesplicing:
            if depth == 0:
                raise Exception("!!!!")
            return (
                Symbol("unquote-splicing"),
                _expand_quasiquote(expr[1], env, depth - 1),
            )
        elif car(expr) == _quasiquote:
            return (
                Symbol("quasiquote"),
                _expand_quasiquote(expr[1], env, depth + 1),
            )
        else:
            fst = car(expr)
            if isPair(fst) and car(fst) == _unquotesplicing:
                unquote_args = cdr(fst)
                if not isPair(unquote_args):
                    raise Exception("Invalid args to unquote")
                return _append(
                    (
                        trampoline(evaluate(car(unquote_args), env, lambda x: x)),
                        (_expand_quasiquote(cdr(expr), env, depth), ()),
                    ),
                )

            return (
                _expand_quasiquote(expr[0], env, depth),
                _expand_quasiquote(expr[1], env, depth),
            )
    else:
        return expr


def eval_quote(arg_exprs: ProperList[Expr], _env: Env, cont: InterpCont) -> Thunk:
    """
    Syntax: (quote <datum>)
    (quote <datum>) evaluates to <datum>
    """
    logger.debug(f"Evaluating quote: {arg_exprs}")

    m = match_type_contract((lambda _: True, ()), arg_exprs)
    if not m:
        raise Exception("!")
    arg_exprs = cast(ConsCell[Expr, Null], arg_exprs)

    return lambda: cont(car(arg_exprs))


def eval_quasiquote(arg_exprs: ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    """
    Syntax: (quasiquote <qq template>)
    If no "unquote" appears within the <qq template>,
    evaluating (quasiquote <qq template>) is equivalent to evaluating (quote <qq template>).
    Sub-expressions wrapped in "unquote" are evaluated and inserted into the structure.
    """
    m = match_type_contract((lambda _: True, ()), arg_exprs)
    if not m:
        raise Exception("!")
    arg_exprs = cast(ConsCell[Expr, Null], arg_exprs)

    expr = car(arg_exprs)
    logger.debug(f"Evaluating quasiquote: {expr}")
    expanded = _expand_quasiquote(expr, env)
    return lambda: cont(expanded)


def evaluate(expr: Atom | ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    logger.debug(f"Evaluating: {expr}")
    if not isAtom(expr):
        expr = cast(ConsCell[Expr, ProperList[Expr]], expr)
        fst = car(expr)
        rest = cdr(expr)

        # (special forms)
        if fst == Symbol("define"):
            return eval_define(rest, env, cont)
        if fst == Symbol("begin"):
            return eval_begin(rest, env, cont)
        if fst == Symbol("if"):
            return eval_if(rest, env, cont)
        if fst == Symbol("let"):
            return eval_let(rest, env, cont)
        if fst == Symbol("letrec"):
            return eval_letrec(rest, env, cont)
        if fst == Symbol("lambda"):
            return eval_lambda(rest, env, cont)
        if fst == Symbol("set!"):
            return eval_set(rest, env, cont)
        if fst == Symbol("quote"):
            return eval_quote(rest, env, cont)
        if fst == Symbol("quasiquote"):
            return eval_quasiquote(rest, env, cont)

        def helper(func):
            return lambda: eval_args(
                rest,
                env,
                lambda args: exec_apply((func, (args, ())), env, cont),
            )

        return evaluate(fst, env, helper)

    elif isinstance(expr, Symbol):
        res = env.find(expr)
        logger.debug(f"Evaluating Symbol: {expr} to: {res}")

        return lambda: cont(env.find(expr))
    elif isinstance(expr, Procedure):
        return lambda: cont(expr)
    elif isinstance(expr, Error):
        raise Exception(f"Cannot evaluate error: {expr}")
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
#                  BUILT-IN PROCEDURES                    #
###########################################################


def exec_isPair(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    m = match_type_contract((lambda _: True, ()), args_expr)
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[Expr, Null], args_expr)

    return cont(isPair(car(args_expr)))


def exec_isNull(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    m = match_type_contract((lambda _: True, ()), args_expr)
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[Expr, Null], args_expr)

    return cont(isNull(car(args_expr)))


def exec_isNumber(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    m = match_type_contract((lambda _: True, ()), args_expr)
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[Expr, Null], args_expr)

    return cont(isNumber(car(args_expr)))


def exec_isSymbol(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    m = match_type_contract((lambda _: True, ()), args_expr)
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[Expr, Null], args_expr)

    return cont(isinstance(car(args_expr), Symbol))


def exec_isBool(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    m = match_type_contract((lambda _: True, ()), args_expr)
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[Expr, Null], args_expr)
    return cont(isinstance(car(args_expr), bool))


def exec_isString(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    m = match_type_contract((lambda _: True, ()), args_expr)
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[Expr, Null], args_expr)
    return cont(isinstance(car(args_expr), str))


def exec_isAtom(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    m = match_type_contract((lambda _: True, ()), args_expr)
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[Expr, Null], args_expr)
    return cont(not isPair(car(args_expr)))


def exec_numeric_eq(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    m = match_type_contract(isNumber, args_expr)
    if not m:
        raise Exception("!")

    args = cons_list_to_python_list(args_expr)
    args = cast(list[int | float], args)
    fst = args[0]
    for val in args[1:]:
        if val != fst:
            return cont(False)
    return cont(True)


def exec_bool_eq(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    """Returns #t if all the arguments are #t or all are #f."""
    m = match_type_contract(lambda x: isinstance(x, bool), args_expr)
    if not m:
        raise Exception("!")

    args = cons_list_to_python_list(args_expr)

    args = cast(list[bool], args)
    if len(args) == 0:
        return cont(True)
    fst = args[0]
    for val in args[1:]:
        if val != fst:
            return cont(False)
    return cont(True)


def exec_symbol_eq(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    """Returns #t if all the arguments have the same naems in the sense of string=?"""
    m = match_type_contract(
        lambda x: isinstance(x, Symbol),
        args_expr,
    )
    if not m:
        raise Exception("!")

    args = cons_list_to_python_list(args_expr)

    if len(args) == 0:
        return cont(True)

    args = cast(list[bool], args)
    fst = args[0]
    for val in args[1:]:
        if val != fst:
            return cont(False)
    return cont(True)


def exec_string_eq(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    """
    Returns #t if all the strings are:
    - the same length and
    - contain exactly the same characters in the same positions
    """
    m = match_type_contract(lambda x: isinstance(x, str), args_expr)
    if not m:
        raise Exception("!")

    if isNull(args_expr):
        return cont(True)

    args = cons_list_to_python_list(args_expr)
    if len(args) == 0:
        return cont(True)

    fst = args[0]
    for val in args[1:]:
        if val != fst:
            return cont(False)
    return cont(True)


def exec_eq(args: ProperList[Expr], env: Env, cont) -> bool:
    """
    The most-discriminating equivalence predicate, relies on pointer-equivalence.

    Undefined for:
    Pairs (eq? '(a) '(a))
    Strings (eq? "A" "A")
    Numbers (eq? 2 2)
    """
    m = match_type_contract((lambda _: True, (lambda _: True, ())), args)
    if not m:
        raise Exception("!")

    args = cast(ConsCell[Expr, ConsCell[Expr, Null]], args)

    fst = car(args)
    rest = cdr(args)
    snd = car(rest)

    if isNull(fst) and isNull(snd):
        return cont(True)
    elif isPair(fst) or isPair(snd):
        return cont(False)
    elif isinstance(fst, float) and isinstance(snd, float):
        # undefined, but this is better than returning false
        return cont(fst == snd)
    elif isinstance(fst, int) and isinstance(snd, int):
        # undefined, but this is better than returning false
        return cont(fst == snd)
    elif isinstance(fst, Symbol) and isinstance(snd, Symbol):
        return cont(fst == snd)
    elif isinstance(fst, str) and isinstance(snd, str):
        # undefined, but this is better than returning false
        return cont(fst == snd)

    return cont(False)


def isNonNullProperList(l: ProperList[P]) -> TypeGuard[ConsCell[P, ProperList[P]]]:
    return not isNull(l)


def exec_eqv(args: ProperList[Expr], env: Env, cont) -> bool:
    """
    Returns true if 2 values are normally considered the same object.
    """
    m = match_type_contract((lambda _: True, (lambda _: True, ())), args)
    if not m:
        raise Exception("!")

    args = cast(ConsCell[Expr, ConsCell[Expr, Null]], args)

    fst = car(args)
    rest = cdr(args)
    snd = car(rest)

    if isNull(fst) and isNull(snd):
        return cont(True)
    elif isPair(fst) or isPair(snd):
        return cont(False)
    elif type(fst) is type(snd):
        return cont(fst == snd)
    return cont(False)


def exec_add(args_expr: ProperList[Expr], env: Env, cont) -> int | float:
    """
    Syntax: (+ z1 ...)
    Return the sum of their arguments.
    """
    m = match_type_contract(isNumber, args_expr)
    if not m:
        raise Exception("!")

    args_expr = cast(ConsCell[Expr, ConsCell[Expr, Null]], args_expr)
    args = cons_list_to_python_list(args_expr)
    if len(args) == 0:
        return cont(0)
    # for arg in args:
    #     if not isNumber(arg):
    #         raise Exception("`Add` requires numeric inputs, but received: {}")
    args = cast(list[int | float], args)
    return cont(reduce(lambda x, y: x + y, args))


def exec_sub(args_expr: ProperList[Expr], env: Env, cont) -> int | float:
    """
    Syntax: (- z1 z2 ...)
    Returns the difference of the arguments, associating to the left.
    With one argument, return the additive inverse.
    """
    m = match_type_contract((isNumber, isNumber), args_expr)
    if not m:
        raise Exception("!")

    args_expr = cast(ConsCell[Expr, ConsCell[Expr, Null]], args_expr)
    args = cons_list_to_python_list(args_expr)
    # if len(args) == 0:
    #     raise Exception("No args passed to `sub`")
    # for arg in args:
    #     if not isNumber(arg):
    #         raise Exception("`Sub` requires numeric inputs, but received: {}")
    args = cast(list[int | float], args)

    if len(args) == 1:
        return cont(-args[0])
    return cont(reduce(lambda x, y: x - y, args))


def exec_mul(args_expr: ProperList[Expr], env: Env, cont) -> int | float:
    """
    Syntax: (* z1 ...)
    Return the product of their arguments.
    """
    m = match_type_contract(isNumber, args_expr)
    if not m:
        raise Exception("!")

    args_expr = cast(ConsCell[Expr, ConsCell[Expr, Null]], args_expr)

    args = cons_list_to_python_list(args_expr)
    if len(args) == 0:
        return cont(1)

    args = cast(list[int | float], args)

    return cont(reduce(lambda x, y: x * y, args))


def exec_div(args_expr: ProperList[Expr], env: Env, cont) -> int | float:
    """
    Syntax: (/ z1 z2 ...)
    Returns the quotient of the arguments, associating to the left.
    With one argument, return the multiplicative inverse.
    """
    m = match_type_contract((isNumber, isNumber), args_expr)
    if not m:
        raise Exception("!")

    args_expr = cast(ConsCell[Expr, ConsCell[Expr, Null]], args_expr)
    args = cons_list_to_python_list(args_expr)

    args = cast(list[int | float], args)

    if len(args) == 1:
        return cont(1 / args[0])
    return cont(reduce(lambda x, y: x / y, args))


def exec_lt(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    """
    Syntax: (< x1 x2 x3 ...)
    Return #t if their arguments are monotonically increasing, and #f otherwise.
    """

    def gt_reduce(values: list[float | int]):
        if len(values) == 1:
            return True
        a = values[0]
        b = values[1]
        if a >= b:
            return False
            # return cont(False)
        return gt_reduce(values[1:])

    args = cons_list_to_python_list(args_expr)
    for arg in args:
        if not isNumber(arg):
            raise Exception("`mul` requires numeric inputs, but received: {}")
    args = cast(list[int | float], args)

    return cont(gt_reduce(args))


def exec_gt(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    """
    Syntax: (> x1 x2 x3 ...)
    Return #t if their arguments are monotonically decreasing, and #f otherwise.
    """

    def gt_reduce(values: list[float | int]):
        if len(values) == 1:
            return True
        a = values[0]
        b = values[1]
        if a <= b:
            return False
        return gt_reduce(values[1:])

    args = cons_list_to_python_list(args_expr)
    for arg in args:
        if not isNumber(arg):
            raise Exception("`mul` requires numeric inputs, but received: {}")
    args = cast(list[int | float], args)
    return cont(gt_reduce(args))


def exec_not(args_expr: ProperList[Expr], env: Env, cont) -> bool:
    """
    Syntax: (not <obj>)
    Returns #t if obj is false, and returns #f otherwise.
    """
    # Accepts any type
    m = match_type_contract((lambda _: True, ()), args_expr)
    if not m:
        raise Exception("!")

    if isPair(args_expr):
        if not isNull(cdr(args_expr)):
            raise Exception("More than one arg provided to `not`")
        if not isinstance(car(args_expr), bool):
            return cont(False)
        return cont(not car(args_expr))
    raise Exception("No arguments provided to `not`")


def exec_cons(args: ProperList[Expr], env: Env, cont) -> ConsCell:
    """
    (cons obj1 obj2)
    Returns a newly allocated pair whose car is obj1 and whose cdr is obj2.
    The pair is guaranteed to be different (in the sense of eqv?) from every existing object.
    """
    m = match_type_contract((lambda _: True, (lambda _: True, ())), args)
    if not m:
        raise Exception("!")
    args = cast(ConsCell[Expr, ConsCell[Expr, Null]], args)

    fst = car(args)
    rest = cdr(args)

    snd = car(rest)
    return cont(cons(fst, snd))


def exec_car(args_expr: ProperList[Expr], env: Env, cont) -> Expr:
    """
    Syntax: (car <pair>)
    Returns the contents of the car field of pair.
    Note that it is an error to take the car of the empty list.
    """
    logger.debug(f"Evaluating `car` on: {args_expr}")
    m = match_type_contract((isPair, ()), args_expr)
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[ConsCell[Expr, Expr], Null], args_expr)
    return cont(car(car(args_expr)))


def exec_cdr(args_expr: ProperList[Expr], env: Env, cont) -> Expr:
    """
    Syntax: (cdr <pair>)
    Returns the contents of the cdr field of pair.
    Note that it is an error to take the cdr of the empty list.
    """
    logger.debug(f"Evaluating `cdr` on: {args_expr}")
    m = match_type_contract((isPair, ()), args_expr)
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[ConsCell, Null], args_expr)
    return cont(cdr(car(args_expr)))


def exec_reverse(args_expr: ProperList[Expr], env: Env, cont) -> ProperList[Expr]:
    """
    Syntax: (reverse <list>)
    Returns a newly allocated list consisting of the elements of list in reverse order.
    """
    # todo: use real isProperList check
    m = match_type_contract(lambda x: isPair(x) or isNull(x), args_expr)
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[ProperList[Expr], Null], args_expr)
    arg = car(args_expr)
    return cont(reverse(arg))


def exec_length(args_expr: ProperList[Expr], env: Env, cont) -> int:
    """
    Syntax: (length <list>)
    Returns the length of <list>
    """
    m = match_type_contract((lambda x: isPair(x) or isNull(x), ()), args_expr)
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[ProperList[Expr], Null], args_expr)

    arg = car(args_expr)
    return cont(length(arg))


def _concat(list1: Expr, list2: Expr) -> Expr:
    if isNull(list1):
        return list2
    if isNull(list2):
        if not isPair(list1):
            raise Exception("!!!")
        return list1
    if not isPair(list1):
        raise Exception("First arg to concat must be a list")
    return (car(list1), _concat(cdr(list1), list2))


def _append(expr: ProperList[Expr]):
    if isNull(expr):
        return ()
    m = match_type_contract(
        (lambda _: True, lambda x: isPair(x) or isNull(x)), reverse(expr)
    )
    if not m:
        raise Exception(f"! {expr}")

    expr = cast(ConsCell, expr)

    fst = car(expr)
    rest = cdr(expr)
    if isNull(fst):
        return _append(rest)

    if isNull(rest):
        return fst

    return _concat(fst, _append(rest))


# APPEND HAS A MORE COMPLEX TYPE CONTRACT
def exec_append(expr: ProperList[Expr], env: Env, cont) -> Expr:
    """
    Syntax: (append <list> …)

    The last argument, if there is one, can be of any type.

    Returns a list consisting of the elements of the first list
    followed by the elements of the other lists.
    If there are no arguments, the empty list is returned.
    If there is exactly one argument, it is returned.
    Otherwise the resulting list is always newly allocated,
    except that it shares structure with the last argument.
    An improper list results if the last argument is not a proper list.
    """
    if isNull(expr):
        return ()
    m = match_type_contract(
        (lambda _: True, lambda x: isPair(x) or isNull(x)), reverse(expr)
    )
    if not m:
        raise Exception(f"! {expr}")

    expr = cast(ConsCell, expr)
    return cont(_append(expr))


def exec_apply(args_expr: ProperList[Expr], env: Env, cont) -> Expr:
    """
    Syntax: (apply <proc> <arg1> … <args>)
    The apply procedure calls proc with the elements of the list
    (append (list arg1 …) args) as the actual arguments.
    """
    m = match_type_contract(
        (
            lambda x: callable(x)
            or isinstance(x, Procedure)
            or isinstance(x, Continuation),
            (lambda x: isPair(x) or isNull(x), ()),
        ),
        args_expr,
    )
    if not m:
        raise Exception("!")

    args_expr = cast(ConsCell[Procedure, ConsCell[ProperList[Expr], Null]], args_expr)

    f = car(args_expr)
    rest = cdr(args_expr)
    args = car(rest)

    if callable(f):
        # apply a builtin procedure
        return apply_primitive_procedure(f, args, env, cont)
    elif isinstance(f, Continuation):
        # apply a continuation
        return apply_continuation(f, args, env, dynamic_wind_stack[:])
    elif isinstance(f, Procedure):
        # apply a user-defined procedure
        return apply_procedure(f, args, cont)
    else:
        raise Exception(
            f"Unimplemented -- tried to apply a non procedure or builtin function: {expr}"
        )


def exec_display(args_expr: ProperList[Expr], env: Env, cont) -> Expr:
    # todo: this shouldn't use pformat -- should display a quoted version of the data
    m = match_type_contract(
        (lambda x: True, ()),
        args_expr,
    )
    if not m:
        raise Exception("!")
    args_expr = cast(ConsCell[Expr, Null], args_expr)

    print(car(args_expr), end="")
    return ()


def exec_newline(expr: ProperList[Expr], env: Env, cont) -> Expr:
    if not isNull(expr):
        raise Exception("`newline` takes no arguments.")
    print()
    return ()


def exec_pretty_print(expr: ProperList[Expr], env: Env, cont) -> Expr:
    if isPair(expr):
        if isNull(cdr(expr)):
            pretty_print(car(expr))
            return ()
    raise Exception("`pretty-print` should only recieve one argument.")


def exec_dynamic_wind(arg_exprs: ProperList[Expr], env: Env, cont: InterpCont) -> Thunk:
    """
    procedure: (dynamic-wind before thunk after)

    Calls <thunk> without arguments and returns the result.

    - <before> is called whenever execution enters the dynamic extent of the call to <thunk>
    - <after> is called whenever it exits that dynamic extent.

    The "dynamic extent" of a procedure call is the period between when the call is initiated and when it returns.
    Because of call/cc, the dynamic extent is not always a single connected time-period.
    """
    global dynamic_wind_stack

    m = match_type_contract(
        (
            lambda x: isinstance(x, Procedure),
            (
                lambda y: isinstance(y, Procedure),
                (lambda z: isinstance(z, Procedure), ()),
            ),
        ),
        arg_exprs,
    )
    if not m:
        raise Exception("!")
    arg_exprs = cast(
        ConsCell[Procedure, ConsCell[Procedure, ConsCell[Procedure, Null]]], arg_exprs
    )

    before = car(arg_exprs)
    body = cadr(arg_exprs)
    after = caddr(arg_exprs)

    def run_before(_):
        dynamic_wind_stack.append((before, after))

        def run_body(result):
            return evaluate(
                after.body, env, lambda _: (dynamic_wind_stack.pop(), cont(result))[1]
            )

        return evaluate(body.body, env, run_body)

    return evaluate(before.body, env, run_before)


def exec_callcc(arg_exprs: ProperList[Expr], env: Env, k: InterpCont) -> Thunk:
    """
    Procedure: (call/cc proc)
    It is an error if proc does not accept one argument.
    Packages the current continuation as an “escape procedure” and passes it as an argument to <proc>.
    If the escape procedure is called, whatever continuation is in effect is abandoned,
    and replaced with the continuation that was in effect when the escape procedure was created.
    """
    # if isPair(arg_exprs):
    if not isNonNullProperList(arg_exprs):
        raise Exception("Call/cc requires procedure input, but recieved no arg!")

    f_expr = car(arg_exprs)

    if isPair(f_expr) and isNull(cdr(f_expr)):
        f_expr = car(f_expr)

    f = f_expr
    if not isinstance(f, Procedure):
        raise Exception("Call/cc requires procedure input")

    # snapshot the dynamic-wind state
    cont = Continuation(k, dynamic_wind_stack[:])
    return evaluate(f.body, Env(f.parms, (cont, ()), env), k)


def standard_env():
    env = Env()
    env.bindings = {
        "+": exec_add,
        "-": exec_sub,
        "*": exec_mul,
        "/": exec_div,
        "<": exec_lt,
        ">": exec_gt,
        "not": exec_not,
        # Type Predicates
        "pair?": exec_isPair,
        "null?": exec_isNull,
        "atom?": exec_isAtom,  # todo: this should be removed
        "boolean?": exec_isBool,
        "number?": exec_isNumber,
        "string?": exec_isString,
        "symbol?": exec_isSymbol,
        # Equivalence Predicates
        "=": exec_numeric_eq,
        "boolean=?": exec_bool_eq,
        "symbol=?": exec_symbol_eq,
        "string=?": exec_string_eq,
        "eq?": exec_eq,
        "eqv?": exec_eqv,
        # List Procedures
        "cons": exec_cons,
        "car": exec_car,
        "cdr": exec_cdr,
        "list": lambda args, _env, k: k(args),
        "append": exec_append,
        "length": exec_length,
        "reverse": exec_reverse,  # needs a test
        "apply": exec_apply,
        # Control-Flow Procedures
        "dynamic-wind": exec_dynamic_wind,
        "call/cc": exec_callcc,
        # UNTESTED:
        # "eval": lambda expr: trampoline(evaluate(expr, env, lambda x: x)),
        # InPort Procedures
        "open-input-file": lambda fname: InPort(open(fname, "r")),
        "read": lambda inport: read(inport),
        # OutPort Procedures
        # todo: unimplemented
        # 'open-output-file': lambda fname: OutPort(open(fname, 'w')),
        # 'write': lambda obj, outport: lambda: outport.file.write(str(obj)),
        # Todo: if second arg is present, use it as OutPort
        "display": exec_display,
        "pretty-print": exec_pretty_print,
        "newline": exec_newline,
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
