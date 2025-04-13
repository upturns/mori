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
import math
import re
from functools import reduce
from typing import Callable


class Symbol:
    name: str

    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"#<Symbol: {self.name}>"

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
    tokenizer = r'''\s*(,@|[('`,)]|"(?:[\\].|[^\\"])*"|;.*|[^\s('"`,;)]*)(.*)'''
    def __init__(self, file):
        self.file = file
        self.line = ''

    def next_token(self) -> "Expr":
        "Return the next token, reading new text into line buffer if needed."
        while True:
            if self.line == '':
                self.line = self.file.readline()
            if self.line == '':
                return EOF_OBJECT
            m = re.match(InPort.tokenizer, self.line)
            if m:
                token, self.line = m.groups()
                if token != '' and not token.startswith(';'):
                    return token


class OutPort:
    "An output port"
    def __init__(self, file):
        self.file = file


Expr = ( int
        | float
        | str
        | None
        | Symbol
        | Procedure
        | Error
        | list["Expr"]
        | Callable[..., "Expr"]
        | InPort
        | OutPort
        )

EOF_OBJECT = Symbol('#<eof-object>')


dynamic_wind_stack = []  # Stack of (before_expr, after_expr)


class Env:
    outer: "Env | None"
    bindings: dict[str, Expr | Callable[..., Expr]]

    def __init__(self, params=(), args=(), outer=None):
        self.outer = outer
        self.bindings = dict(zip([x.name for x in params], args))

    def find(self, var: Symbol) ->  Expr | Callable[..., Expr]:
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


def evaluate_define(arg_exprs: list[Expr], env: Env, cont):
    header = arg_exprs[0]
    body = arg_exprs[1]

    if isinstance(header, Symbol):
        return lambda: evaluate(body, env, lambda val: (
        env.bindings.update({header.name: val}),
        lambda: cont(None)
        )[1])

    if not isinstance(header, list):
        raise Exception("Malformed definition (1)!")

    name = header[0]

    if not isinstance(name, Symbol):
        raise Exception("Malformed definition (2)!")

    params = header[1:]
    p = Procedure(params, body, env)
    env.bindings[name.name] = p

    return lambda: cont(None)


def eval_sequence(exprs: list[Expr], env: Env, cont):
    """
    evaluates a sequence of expressions in order,
    discarding intermediate values and keeping the result of the last one
    """
    first, *rest = exprs

    if not rest:
        # Last expression: evaluate with original continuation
        return lambda: evaluate(first, env, cont)

    # Otherwise: evaluate `first`, discard result, continue with rest
    return lambda: evaluate(first, env, 
        lambda _ignored_value: lambda: eval_sequence(rest, env, cont)
    )


def evaluate_begin(exprs: list[Expr], env: Env, cont):
    if not exprs:
        raise Exception("begin with no expressions")
    return eval_sequence(exprs, env, cont)


def evaluate_if(arg_exprs: list[Expr], env: Env, cont):
    cond_expr = arg_exprs[0]
    conseq_expr = arg_exprs[1]
    alt_expr = arg_exprs[2]

    return lambda: evaluate(cond_expr, env, lambda cond:
            (lambda: evaluate(conseq_expr, env, cont)) if cond else
            lambda: evaluate(alt_expr, env, cont)
            )


# cont should be a function that takes a list of exprs
def evaluate_args(arg_exprs: list[Expr], env: Env, cont):
    if len(arg_exprs) == 0:
        return lambda: cont([])

    first, *rest = arg_exprs

    if not rest:
        # Last expression: evaluate with original continuation
        return lambda: evaluate(first, env, lambda val: lambda: cont([val]))

    # Otherwise: evaluate `first`, discard result, continue with rest
    return lambda: evaluate(first, env, 
        lambda val: evaluate_args(rest, env,
                                  lambda values: lambda: cont([val] + values))
    )


def evaluate_let(arg_exprs: list[Expr], env: Env, cont):
    binding_exprs = arg_exprs[0]
    body_expr = arg_exprs[1]

    if not isinstance(binding_exprs, list):
        raise Exception("Invalid bindings in let!")

    names = []
    val_exprs = []
    for bexp in binding_exprs:
        if not isinstance(bexp, list):
            raise Exception("Invalid binding form in let (1)!")
        var_expr = bexp[0]
        if not isinstance(var_expr, Symbol):
            raise Exception("Invalid binding form in let (2)!")
        names.append(var_expr.name)
        val_exprs.append(bexp[1])

    def with_values(values):
        child_env = Env((), (), env)
        child_env.bindings.update(dict(zip(names, values)))
        return lambda: evaluate(body_expr, child_env, cont)

    return evaluate_args(val_exprs, env, with_values) 


def evaluate_letrec(arg_exprs: list[Expr], env: Env, cont):
    binding_exprs = arg_exprs[0]
    body_expr = arg_exprs[1]

    if not isinstance(binding_exprs, list):
        raise Exception("Invalid bindings in letrec!")

    names = []
    val_exprs = []
    child_env = Env((), (), env)
    for binding_expr in binding_exprs:
        if not isinstance(binding_expr, list):
            raise Exception("Invalid binding in letrec!")

        var_expr = binding_expr[0]

        if not isinstance(var_expr, Symbol):
            raise Exception("Invalid variable in letrec binding")

        names.append(var_expr.name)
        val_exprs.append(binding_expr[1])
        child_env.bindings[var_expr.name] = None

    def with_values(values):
        child_env.bindings.update(dict(zip(names, values)))
        return lambda: evaluate(body_expr, child_env, cont)

    return evaluate_args(val_exprs, child_env, with_values) 


def evaluate_lambda(arg_exprs: list[Expr], env: Env, cont):
    param_exprs = arg_exprs[0]
    body_expr = arg_exprs[1]
    return lambda: cont(Procedure(param_exprs, body_expr, env))


def eval_callcc(expr, env, k):
    [f_expr] = expr

    def apply_fn(f):
        # snapshot the dynamic-wind state
        cont = Continuation(k, dynamic_wind_stack[:])
        return evaluate(f.body, Env(f.parms, [cont], env), k)

    return lambda: evaluate(f_expr, env, apply_fn)


def eval_set(arg_exprs: list[Expr], env: Env, cont):
    sym_expr, val_expr = arg_exprs
    if not isinstance(sym_expr, Symbol):
        raise Exception("Cannot use `set!` with a non-Symbol variable name")
    return lambda: evaluate(val_expr, env, lambda val:
                            lambda: cont(env.set(sym_expr, val)))


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
    return run_afters(len(from_stack) - 1, lambda: func.f(*args))


def eval_dynamic_wind(expr, env, cont):
    global dynamic_wind_stack
    before, body, after = expr
    def run_before(_):
        dynamic_wind_stack.append((before, after))

        def run_body(result):
            return evaluate(after.body, env, lambda _: (
                dynamic_wind_stack.pop(),
                cont(result)
            )[1])

        return lambda: evaluate(body.body, env, run_body)

    return lambda: evaluate(before.body, env, run_before)


def evaluate(expr: Expr, env: Env, cont) -> Expr:
    if isinstance(expr, list):
        func_expr = expr[0]
        arg_exprs = expr[1:]
        # (special forms)
        # these functions work even if the global env is empty
        if func_expr == Symbol("define"):
            return evaluate_define(arg_exprs, env, cont)
        if func_expr == Symbol("begin"):
            return evaluate_begin(arg_exprs, env, cont)
        if func_expr == Symbol("cond"):
            return evaluate_if(arg_exprs, env, cont)
        if func_expr == Symbol("let"):
            return evaluate_let(arg_exprs, env, cont)
        if func_expr == Symbol("letrec"):
            return evaluate_letrec(arg_exprs, env, cont)
        if func_expr == Symbol("lambda"):
            return evaluate_lambda(arg_exprs, env, cont)
        if func_expr == Symbol("call/cc"):
            return eval_callcc(arg_exprs, env, cont)
        if func_expr == Symbol("quote"):
            return lambda: cont(*arg_exprs)
        if func_expr == Symbol("set!"):
            return eval_set(arg_exprs, env, cont)
        if func_expr == Symbol("dynamic-wind"):
            return lambda: evaluate_args(arg_exprs, env, lambda args: eval_dynamic_wind(args, env, cont))

        def helper(func):
            if callable(func):
                return lambda: evaluate_args(arg_exprs, env, lambda args: lambda: cont(func(*args)))
            elif isinstance(func, Continuation):
                # apply a continuation
                return lambda: evaluate_args(arg_exprs, env, lambda args: lambda: apply_continuation(func, args, env, dynamic_wind_stack[:]))
            elif isinstance(func, Procedure):
                # apply a procedure
                return lambda: evaluate_args(arg_exprs, env, lambda args:
                                     lambda: evaluate(func.body, Env(func.parms, args, func.env), cont))
            else:
                raise Exception(f"Unimplemented -- tried to apply a non procedure or builtin function: {expr}")
        return evaluate(func_expr, env, helper)

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


def shared_prefix_length(stack1, stack2):
    i = 0
    while i < len(stack1) and i < len(stack2) and stack1[i] == stack2[i]:
        i += 1
    return i


def readchar(inport):
    "Read the next character from an input port."
    if inport.line != '':
        ch, inport.line = inport.line[0], inport.line[1:]
        return ch
    else:
        return inport.file.read(1) or EOF_OBJECT


def read(inport) -> Expr:
    "Read a Scheme expression from an input port."
    def read_ahead(token):
        if '(' == token: 
            L = []
            while True:
                token = inport.next_token()
                if token == ')':
                    return L
                else:
                    L.append(read_ahead(token))
        elif ')' == token:
            raise SyntaxError('unexpected )')
        elif token in quotes:
            return [quotes[token], read(inport)]
        elif token is EOF_OBJECT:
            raise SyntaxError('unexpected EOF in list')
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
    "'":_quote,
    # "`":_quasiquote,
    # ",":_unquote,
    # ",@":_unquotesplicing
}


def atom(token) -> Expr:
    'Numbers become numbers; #t and #f are booleans; "..." string; otherwise Symbol.'
    if token == '#t':
        return True
    elif token == '#f':
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


def trampoline(f):
    while callable(f):
        f = f()
    return f


def standard_env():
    env = Env()
    env.bindings = {
        '+': lambda *args: sum(args),
        '-': lambda *args: reduce(lambda x, y: x - y, args),
        '*': lambda *args: math.prod(args),
        '/': lambda *args: reduce(lambda x, y: x / y, args),
        '=': lambda a, b: a == b,
        '<': lambda a, b: a < b,
        'length': lambda lst: len(lst),
        'reverse': lambda lst: lst[::-1],
        'cons': lambda a, b: [a] + b,
        'eval': lambda expr: lambda: evaluate(expr, env, lambda x: x),
        # InPort Procedures
        'open-input-file': lambda fname: InPort(open(fname, 'r')),
        'read': lambda inport: lambda: read(inport),
        # OutPort Procedures
        'open-output-file': lambda fname: OutPort(open(fname, 'w')),
        'write': lambda obj, outport: lambda: outport.file.write(str(obj)),
        # Todo: if second arg is present, use it as OutPort
        'display': lambda *args: print(args),

    }
    return env
