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
    def __init__(self, f):
        self.f = f


Expr = ( int
        | float
        | str
        | None
        | Symbol
        | Procedure
        | Error
        | list["Expr"]
        | Callable[..., "Expr"]
        )

EOF_OBJECT = Symbol('#<eof-object>')


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


def eval_callcc(arg_exprs: list[Expr], env: Env, cont):
    [func_expr] = arg_exprs
    return lambda: evaluate(func_expr, env, lambda func:
        lambda: evaluate(func.body,  Env(func.parms, [Continuation(cont)], func.env), cont)
    )


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

        def helper(func):
            if callable(func):
                return lambda: evaluate_args(arg_exprs, env, lambda args: lambda: cont(func(*args)))
            elif isinstance(func, Continuation):
                # apply a continuation
                return lambda: evaluate_args(arg_exprs, env, lambda args: lambda: func.f(*args))
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

    raise Exception("Unhandled")


class InPort(object):
    "An input port. Retains a line of chars."
    tokenizer = r'''\s*(,@|[('`,)]|"(?:[\\].|[^\\"])*"|;.*|[^\s('"`,;)]*)(.*)'''
    def __init__(self, file):
        self.file = file
        self.line = ''

    def next_token(self) -> Expr:
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
        # elif token in quotes:
        #     return [quotes[token], read(inport)]
        elif token is EOF_OBJECT:
            raise SyntaxError('unexpected EOF in list')
        else:
            return atom(token)
    # body of read:
    token1 = inport.next_token()
    return EOF_OBJECT if token1 is EOF_OBJECT else read_ahead(token1)

# quotes = {"'":_quote, "`":_quasiquote, ",":_unquote, ",@":_unquotesplicing}


def atom(token) -> Expr:
    'Numbers become numbers; #t and #f are booleans; "..." string; otherwise Symbol.'
    if token == '#t':
        return True
    elif token == '#f':
        return False
    elif token[0] == '"':
        return token[1:-1] #.decode('unicode_escape')
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
        '=': lambda a, b: a == b
    }
    return env
