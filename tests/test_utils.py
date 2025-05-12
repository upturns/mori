from interp import InPort, standard_env, trampoline, read, evaluate
from io import StringIO


def i(s: str, env=None):
    # can't initialize this in the function definition, because that causes it to be reused between calls
    if env is None:
        env = standard_env()
    x = InPort(StringIO(s))
    i = read(x)
    return trampoline(evaluate(i, env, lambda x: x, lambda x, _k: lambda: x)), env
