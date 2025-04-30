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
from typing import Callable, TypeGuard
import logging


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

Thunk = Callable[[], "Thunk" | Expr]
InterpCont = Callable[[Expr], Expr | Thunk]


def extract_bindings(param_exprs, vals_exprs):
    if isNull(param_exprs):
        return {}
    if not isPair(param_exprs):
        if not isinstance(param_exprs, Symbol):
            raise Exception("Must be symbol in binding")
        return {param_exprs.name: vals_exprs}

    fst = param_exprs[0]
    rest = param_exprs[1]

    fst_val = vals_exprs[0]

    if not isinstance(fst, Symbol):
        raise Exception("Binding name must be a symbol")

    return {fst.name: fst_val, **extract_bindings(rest, vals_exprs[1])}


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


def pformat(expr: Expr, indent=0, max_width=80):
    def is_syntax_form(exp: Expr, name):
        return (
            isPair(exp)
            and isinstance(exp[0], Symbol)
            and exp[0].name == name
            and isPair(exp[1])
            and isNull(exp[1][1])
        )

    def collect_list_elements(exp: Expr):
        elems = []
        while isPair(exp):
            elems.append(exp[0])
            exp = exp[1]
        return tuple(elems), exp  # rest will be [] if proper

    def pp(exp: Expr, current_indent):
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


def pretty_print(expr: Expr, indent=0, max_width=80) -> None:
    """Pretty-print a Scheme expression with indentation and shorthand syntax."""
    formatted = pformat(expr, indent)
    print(formatted)


def cons(p: Expr, q: Expr) -> ConsCell:
    return (p, q)


def car(args: ConsCell) -> Expr:
    return args[0]


def cdr(args: ConsCell) -> Expr:
    return args[1]


def cadr(args: ConsCell) -> Expr:
    if not isPair(args[1]):
        raise Exception(f"Malformed list for CADR: {args}")
    return args[1][0]


def caddr(args: ConsCell) -> Expr:
    if length(args) < 3:
        raise Exception("Cannot get CADDR of list with < 3 items.")
    if not isPair(args[1]):
        raise Exception("Malformed list for CADDR!")
    if not isPair(args[1][1]):
        raise Exception("Malformed list for CADDR!")
    return args[1][1][0]


# gets the length of a cons list
def length(lst):
    result = 0
    while (isinstance(lst, list) or isinstance(lst, tuple)) and len(lst) > 0:
        result += 1
        lst = lst[1]
    if not (isinstance(lst, list) or isinstance(lst, tuple)):
        result += 1
    return result


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


def reduce_proper_list(
    exp: ConsCell, f: Callable[[Expr, Expr], Expr], accum: Expr
) -> Expr:
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


def isPair(expr: Expr) -> TypeGuard[ConsCell]:
    return (isinstance(expr, tuple) or isinstance(expr, list)) and len(expr) == 2


def isNull(expr: Expr) -> TypeGuard[tuple[()]]:
    logger.debug(f"Performing null check on: {expr}")
    return (isinstance(expr, tuple) or isinstance(expr, list)) and len(expr) == 0


def isNumber(expr: Expr) -> TypeGuard[int | float]:
    return (isinstance(expr, int) or isinstance(expr, float)) and not isinstance(
        expr, bool
    )


###########################################################
#                SPECIAL FORM EVALUATORS                  #
###########################################################


def evaluate_define(arg_exprs: ConsCell | tuple[()], env: Env, cont):
    if isPair(arg_exprs):
        header = car(arg_exprs)
        body = cadr(arg_exprs)
        logger.debug(f"Evaluating define. Header= {header}")

        if isinstance(header, Symbol):
            return lambda: evaluate(
                body,
                env,
                lambda val: (
                    env.bindings.update({header.name: val}),
                    lambda: cont(None),
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

        return lambda: cont(None)
    raise Exception("No arguments passed to define")


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


def evaluate_begin(exprs: ConsCell | tuple[()], env: Env, cont):
    if isPair(exprs):
        return eval_sequence(exprs, env, cont)
    raise Exception("No arguments passed to begin")


def evaluate_if(args: ConsCell | tuple[()], env: Env, cont):
    if isPair(args):
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
    raise Exception("No arguments passed to if")


# cont should be a function that takes a list of exprs
def evaluate_args(arg_exprs: ConsCell | tuple[()], env: Env, cont):
    if not isPair(arg_exprs):
        return lambda: cont(())

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


def evaluate_let(arg_exprs: ConsCell | tuple[()], env: Env, cont):
    if isPair(arg_exprs):
        binding_exprs = car(arg_exprs)
        body_expr = cadr(arg_exprs)

        if not isPair(binding_exprs):
            raise Exception("Invalid bindings in let!")

        # binding_exprs is a linked list of pairs (k, v)
        # we want to map it into a linked list of just values
        binding_name_exprs = ()
        binding_value_exprs = ()
        b = binding_exprs
        while isPair(b):
            binding = car(b)
            if not isPair(binding):
                raise Exception("Binding must be a pair")
            binding_name_exprs = (car(binding), binding_name_exprs)
            binding_value_exprs = (cadr(binding), binding_value_exprs)
            b = cdr(b)

        def with_values(values):
            child_env = Env(binding_name_exprs, values, env)
            return lambda: evaluate(body_expr, child_env, cont)

        return evaluate_args(binding_value_exprs, env, with_values)
    raise Exception("No arguments passed to `let`")


def evaluate_letrec(arg_exprs: ConsCell | tuple[()], env: Env, cont):
    if isPair(arg_exprs):
        binding_exprs = car(arg_exprs)
        body_expr = cadr(arg_exprs)

        if not isPair(binding_exprs):
            raise Exception("Invalid bindings in letrec!")

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
            if not isinstance(name_expr, Symbol):
                raise Exception("Binding name must be a symbol")

            binding_name_exprs = (name_expr, binding_name_exprs)
            binding_value_exprs = (cadr(binding), binding_value_exprs)

            child_env.bindings[name_expr.name] = ()
            names.append(name_expr.name)

            b = cdr(b)

        names.reverse()

        def with_values(values):
            child_env.bindings.update(
                dict(zip(names, cons_list_to_python_list(values)))
            )
            return lambda: evaluate(body_expr, child_env, cont)

        return evaluate_args(binding_value_exprs, child_env, with_values)
    raise Exception("No arguments passed to `letrec`")


def evaluate_lambda(arg_exprs: ConsCell | tuple[()], env: Env, cont):
    if isPair(arg_exprs):
        param_exprs = car(arg_exprs)
        body_expr = cadr(arg_exprs)

        # If the lambda is a term (lambda (x) x),
        # it will still be parsed as `[lambda [x []] [x []]]`
        if not isPair(body_expr):
            return lambda: cont(Procedure(param_exprs, body_expr, env))

        return lambda: cont(Procedure(param_exprs, body_expr, env))
    raise Exception("No arguments passed to `lambda`")


def eval_callcc(expr: ConsCell | tuple[()], env, k):
    if isPair(expr):
        f_expr = car(expr)

        if isPair(f_expr) and isNull(cdr(f_expr)):
            f_expr = car(f_expr)

        def apply_fn(f):
            # snapshot the dynamic-wind state
            cont = Continuation(k, dynamic_wind_stack[:])
            return evaluate(f.body, Env(f.parms, (cont, ()), env), k)

        return lambda: evaluate(f_expr, env, apply_fn)
    raise Exception("No arguments passed to `callcc`")


def eval_set(arg_exprs: ConsCell | tuple[()], env: Env, cont):
    if isPair(arg_exprs):
        sym_expr = car(arg_exprs)
        val_expr = cadr(arg_exprs)
        if not isinstance(sym_expr, Symbol):
            raise Exception("Cannot use `set!` with a non-Symbol variable name")
        return lambda: evaluate(
            val_expr, env, lambda val: lambda: cont(env.set(sym_expr, val))
        )
    raise Exception("No arguments passed to `set`")


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


def apply_procedure(proc: Procedure, args: Expr, cont):
    logger.debug(f"Applying defined procedure {proc} to {args}")
    return lambda: evaluate(proc.body, Env(proc.parms, args, proc.env), cont)


def apply_primitive_procedure(builtin_func, args: Expr, cont) -> Thunk:
    logger.debug(f"Applying primitive procedure {builtin_func} to {args}")
    return lambda: cont(builtin_func(args))


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


def _expand_quasiquote(expr, env, depth=0):
    if isPair(expr):
        if car(expr) == _unquote:
            if depth == 0:
                return trampoline(evaluate(cadr(expr), env, lambda x: x))
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
                return exec_append(
                    (
                        trampoline(evaluate(cadr(fst), env, lambda x: x)),
                        (_expand_quasiquote(cdr(expr), env, depth), ()),
                    )
                )

            return (
                _expand_quasiquote(expr[0], env, depth),
                _expand_quasiquote(expr[1], env, depth),
            )
    else:
        return expr


def eval_quote(args: ConsCell | tuple[()], env: Env, cont: InterpCont):
    logger.debug(f"Evaluating quote: {args}")
    if isPair(args):
        if isNull(cdr(args)):
            return lambda: cont(args[0])
        return lambda: cont(args)
    raise Exception("No arguments passed to `quote`")


def eval_quasiquote(args, env, cont):
    expr = car(args)
    logger.debug(f"Evaluating quasiquote: {expr}")
    expanded = _expand_quasiquote(expr, env)
    return lambda: cont(expanded)


def evaluate(expr: Expr, env: Env, cont: InterpCont) -> Thunk:
    logger.debug(f"Evaluating: {expr}")
    if isPair(expr):
        fst = car(expr)
        rest = cdr(expr)

        if not isPair(rest) and not isNull(rest):
            raise Exception(
                f"Malformed input expression: {expr}. Must be a proper list!"
            )

        # (special forms)
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
            return eval_quote(rest, env, cont)
            # if isNull(cdr(rest)):
            #     return lambda: cont(rest[0])
            # return lambda: cont(rest)
        if fst == Symbol("quasiquote"):
            return eval_quasiquote(rest, env, cont)
        if fst == Symbol("dynamic-wind"):
            return lambda: evaluate_args(
                rest, env, lambda args: eval_dynamic_wind(args, env, cont)
            )

        def helper(func):
            if callable(func):
                # apply a builtin procedure
                return lambda: evaluate_args(
                    rest, env, lambda args: apply_primitive_procedure(func, args, cont)
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
                    rest, env, lambda args: apply_procedure(func, args, cont)
                )
            else:
                raise Exception(
                    f"Unimplemented -- tried to apply a non procedure or builtin function: {func}"
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
#                  BUILT-IN PROCEDURES                    #
###########################################################


def exec_isPair(args: ConsCell | tuple[()]):
    if isPair(args):
        return isPair(car(args))
    raise Exception("No arguments provided to `pair?`")


def exec_isNull(args: ConsCell | tuple[()]):
    if isPair(args):
        return isNull(car(args))
    raise Exception("No arguments provided to `null?`")


def exec_isNumber(args: ConsCell | tuple[()]):
    if isPair(args):
        return isNumber(car(args))
    raise Exception("No arguments provided to `number?`")


def exec_isSymbol(args: ConsCell | tuple[()]):
    if isPair(args):
        return isinstance(car(args), Symbol)
    raise Exception("No arguments provided to `symbol?`")


def exec_isBool(args: ConsCell | tuple[()]):
    if isPair(args):
        return isinstance(car(args), bool)
    raise Exception("No arguments provided to `boolean?`")


def exec_isString(args: ConsCell | tuple[()]):
    if isPair(args):
        return isinstance(car(args), str)
    raise Exception("No arguments provided to `string?`")


def exec_isAtom(args: ConsCell | tuple[()]):
    if isPair(args):
        return not isPair(car(args))
    raise Exception("No arguments provided to `atom?`")


def exec_eq(args: ConsCell):
    fst = car(args)
    snd = cadr(args)
    return fst == snd


def exec_add(args: ConsCell):
    # todo: verify 2+ args
    def _add_helper(curr, accum):
        return curr + accum

    return reduce_proper_list(args, _add_helper, 0)


def exec_sub(args: ConsCell):
    # todo: verify 2+ args
    def _sub_helper(curr, accum):
        return accum - curr

    rest = cdr(args)
    if not isPair(rest):
        raise Exception("Malformed args for `sub`")
    return reduce_proper_list(rest, _sub_helper, args[0])


def exec_mul(args: ConsCell):
    # todo: verify 2+ args
    def _mul_helper(curr, accum):
        return curr * accum

    return reduce_proper_list(args, _mul_helper, 1)


def exec_div(args: ConsCell):
    # todo: verify 2+ args
    def _div_helper(curr, accum):
        return accum / curr

    rest = cdr(args)
    if not isPair(rest):
        raise Exception("Malformed args for `div`")
    return reduce_proper_list(rest, _div_helper, args[0])


def exec_lt(expr: ConsCell):
    fst = car(expr)
    snd = cadr(expr)
    if not isNumber(fst):
        raise Exception("Non numeric input for LT")
    if not isNumber(snd):
        raise Exception("Non numeric input for LT")
    return fst < snd


def exec_gt(expr: ConsCell):
    fst = car(expr)
    snd = cadr(expr)
    if not isNumber(fst):
        raise Exception("Non numeric input for LT")
    if not isNumber(snd):
        raise Exception("Non numeric input for LT")
    return fst > snd


def exec_not(args: ConsCell | tuple[()]):
    if isPair(args):
        return not car(args)
    raise Exception("No arguments provided to `not`")


def exec_cons(args: ConsCell | tuple[()]):
    if isPair(args):
        if isNull(cdr(args)):
            raise Exception("Only one argument provided to `cons`")
        return cons(car(args), cadr(args))
    raise Exception("No arguments provided to `cons`")


def exec_car(args: ConsCell) -> Expr:
    logger.debug(f"Evaluating `car` on: {args}")
    if not isPair(args[0]):
        raise Exception("The argument to car must be a pair!")
    if not isNull(args[1]):
        raise Exception("Too many arguments provided to car!")
    return car(args[0])


def exec_cdr(args: ConsCell) -> Expr:
    logger.debug(f"Evaluating `cdr` on: {args}")
    if not isPair(args[0]):
        raise Exception("The argument to cdr must be a pair!")
    if not isNull(args[1]):
        raise Exception("Too many arguments provided to cdr!")
    return cdr(args[0])


def exec_reverse(args: ConsCell | tuple[()]):
    if isPair(args):
        return reverse(car(args))
    raise Exception("No arguments provided to `reverse`")


def exec_length(args: ConsCell | tuple[()]):
    if isPair(args):
        return length(car(args))
    raise Exception("No arguments provided to `length`")


def _concat(list1: Expr, list2: ConsCell | tuple[()]) -> ConsCell | tuple[()]:
    if isNull(list1):
        return list2
    if isNull(list2):
        if not isPair(list1):
            raise Exception("!!!")
        return list1
    if not isPair(list1):
        return (list1, list2)
    return (car(list1), _concat(cdr(list1), list2))


def exec_append(expr: ConsCell):
    fst = car(expr)
    snd = cdr(expr)
    if isNull(snd):
        return fst
    if not isPair(snd):
        raise Exception("Second argument to `append` must be a pair")
    return _concat(fst, exec_append(snd))


def exec_apply(expr: Expr) -> Expr:
    if not isPair(expr):
        raise Exception("Apply requires a list of arguments")

    f = car(expr)
    args = cadr(expr)

    if callable(f):
        # apply a builtin procedure
        return trampoline(apply_primitive_procedure(f, args, lambda x: x))
    elif isinstance(f, Continuation):
        # apply a continuation
        return trampoline(apply_continuation(f, args, env, dynamic_wind_stack[:]))
    elif isinstance(f, Procedure):
        # apply a user-defined procedure
        return trampoline(apply_procedure(f, args, lambda x: x))
    else:
        raise Exception(
            f"Unimplemented -- tried to apply a non procedure or builtin function: {expr}"
        )


def exec_display(expr: Expr) -> Expr:
    # todo: this shouldn't use pformat -- should display a quoted version of the data
    if isPair(expr):
        if isNull(cdr(expr)):
            print(car(expr), end="")
            return ()
    raise Exception("`display` should only recieve one argument.")


def exec_newline(expr: Expr) -> Expr:
    if not isNull(expr):
        raise Exception("`newline` takes no arguments.")
    print()
    return ()


def exec_pretty_print(expr: ConsCell | tuple[()]) -> Expr:
    if isPair(expr):
        if isNull(cdr(expr)):
            pretty_print(car(expr))
            return ()
    raise Exception("`pretty-print` should only recieve one argument.")


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
        # Equivalence Predicates
        "=": exec_eq,
        "eq?": exec_eq,
        "length": exec_length,
        "reverse": exec_reverse,
        "cons": exec_cons,
        "car": exec_car,
        "cdr": exec_cdr,
        "append": exec_append,
        "list": lambda args: args,
        "pair?": exec_isPair,
        "null?": exec_isNull,
        "atom?": exec_isAtom,
        "boolean?": exec_isBool,
        "number?": exec_isNumber,
        "string?": exec_isString,
        "symbol?": exec_isSymbol,
        "eval": lambda expr: trampoline(evaluate(expr, env, lambda x: x)),
        # InPort Procedures
        "open-input-file": lambda fname: InPort(open(fname, "r")),
        "read": lambda inport: read(inport),
        # OutPort Procedures
        "apply": exec_apply,
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
