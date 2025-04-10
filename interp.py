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


def evaluate_define(arg_exprs: list[Expr], env: Env):
    header = arg_exprs[0]
    body = arg_exprs[1]

    if isinstance(header, Symbol):
        env.bindings[header.name] = evaluate(body, env)
        return None

    if not isinstance(header, list):
        raise Exception("Malformed definition (1)!")

    name = header[0]

    if not isinstance(name, Symbol):
        raise Exception("Malformed definition (2)!")

    params = header[1:]
    p = Procedure(params, body, env)
    env.bindings[name.name] = p

    return None


def evaluate_begin(arg_exprs: list[Expr], env: Env):
    res = None
    for expr in arg_exprs:
        res = evaluate(expr, env)
    return res


def evaluate_if(arg_exprs: list[Expr], env: Env):
    cond_expr = arg_exprs[0]
    conseq_expr = arg_exprs[1]
    alt_expr = arg_exprs[2]

    cond = evaluate(cond_expr, env)
    if cond:
        return evaluate(conseq_expr, env)
    else:
        return evaluate(alt_expr, env)


def evaluate_let(arg_exprs: list[Expr], env: Env):
    binding_exprs = arg_exprs[0]
    body_expr = arg_exprs[1]

    if not isinstance(binding_exprs, list):
        raise Exception("Invalid bindings in let!")

    child_env = Env((), (), env)
    for binding_expr in binding_exprs:
        if not isinstance(binding_expr, list):
            raise Exception("Invalid binding in let!")

        var_expr = binding_expr[0]

        if not isinstance(var_expr, Symbol):
            raise Exception("Invalid variable in let binding")

        val_expr = binding_expr[1]
        val = evaluate(val_expr, env)
        child_env.bindings[var_expr.name] = val

    return evaluate(body_expr, child_env)


def evaluate_letrec(arg_exprs: list[Expr], env: Env):
    binding_exprs = arg_exprs[0]
    body_expr = arg_exprs[1]

    if not isinstance(binding_exprs, list):
        raise Exception("Invalid bindings in letrec!")

    child_env = Env((), (), env)
    for binding_expr in binding_exprs:
        if not isinstance(binding_expr, list):
            raise Exception("Invalid binding in letrec!")

        var_expr = binding_expr[0]

        if not isinstance(var_expr, Symbol):
            raise Exception("Invalid variable in letrec binding")

        child_env.bindings[var_expr.name] = None

    vals = {}
    for binding_expr in binding_exprs:
        # todo: the `isinstance` checks here are unnecessary, but the type checker wants them.
        if not isinstance(binding_expr, list):
            raise Exception("Invalid binding in letrec!")

        var_expr = binding_expr[0]

        if not isinstance(var_expr, Symbol):
            raise Exception("Invalid variable in letrec binding")
        val_expr = binding_expr[1]
        val = evaluate(val_expr, child_env)

        vals[var_expr.name] = val

    child_env.bindings.update(vals)
    return evaluate(body_expr, child_env)


def evaluate_lambda(arg_exprs: list[Expr], env: Env):
    param_exprs = arg_exprs[0]
    body_expr = arg_exprs[1]
    return Procedure(param_exprs, body_expr, env)


def evaluate(expr: Expr, env: Env) -> Expr:
    if isinstance(expr, list):
        func_expr = expr[0]
        arg_exprs = expr[1:]

        # built-in functions (special forms)
        # these functions work even if the global env is empty
        if func_expr == Symbol("define"):
            return evaluate_define(arg_exprs, env)
        if func_expr == Symbol("begin"):
            return evaluate_begin(arg_exprs, env)
        if func_expr == Symbol("cond"):
            return evaluate_if(arg_exprs, env)
        if func_expr == Symbol("let"):
            return evaluate_let(arg_exprs, env)
        if func_expr == Symbol("letrec"):
            return evaluate_letrec(arg_exprs, env)
        if func_expr == Symbol("lambda"):
            return evaluate_lambda(arg_exprs, env)

        # non-built-in functions
        func = evaluate(func_expr, env)
        args = [evaluate(x, env) for x in expr[1:]]
        if isinstance(func, Procedure):
            # user-defined function
            if len(args) > len(func.parms):
                raise Exception(f"Too many arguments provided to {func_expr}")
            elif len(args) < len(func.parms):
                raise Exception(f"Too few arguments provided to {func_expr}")
            return evaluate(func.body, Env(func.parms, args, func.env))
        elif callable(func):
            # built-in function
            return func(*args)
        else:
            raise Exception(f"Unimplemented -- tried to apply a non procedure or builtin function: {expr}")
    elif isinstance(expr, Symbol):
        return env.find(expr)
    elif isinstance(expr, Procedure):
        return expr
    elif isinstance(expr, Error):
        pass
    elif isinstance(expr, int):
        return expr
    elif isinstance(expr, bool):
        return expr

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
                return eof_object
            m = re.match(InPort.tokenizer, self.line)
            if m:
                token, self.line = m.groups()
                if token != '' and not token.startswith(';'):
                    return token


eof_object = Symbol('#<eof-object>') # Note: uninterned; can't be read


def readchar(inport):
    "Read the next character from an input port."
    if inport.line != '':
        ch, inport.line = inport.line[0], inport.line[1:]
        return ch
    else:
        return inport.file.read(1) or eof_object


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
        elif token is eof_object:
            raise SyntaxError('unexpected EOF in list')
        else:
            return atom(token)
    # body of read:
    token1 = inport.next_token()
    return eof_object if token1 is eof_object else read_ahead(token1)

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


def standard_env():
    env = Env()
    env.bindings = {
        '+': lambda *args: sum(args),
        '-': lambda *args: reduce(lambda x, y: x - y, args),
        '*': lambda *args: math.prod(args),
        '=': lambda a, b: a == b
    }
    return env
