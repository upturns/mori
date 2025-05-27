
# Mori Scheme

This is a work-in-progress R7RS-compatible Scheme interpreter I'm writing in Python to learn about the interpretation process.

The goal is to implement a subset of R7RS which can be used to bootstrap the remainder of the language. More-specifially, I want to provide a subset of scheme forms that can be used to define a macro-expander -- allowing syntax extensions to be written in portable scheme that can run on other Schemes.

- [Mori Scheme](#mori-scheme)
  - [Special Forms](#special-forms)
    - [set](#set)
    - [if](#if)
    - [define](#define)
    - [begin](#begin)
    - [let](#let)
    - [letrec](#letrec)
    - [lambda](#lambda)
    - [quote](#quote)
    - [quasiquote](#quasiquote)
  - [Procedures](#procedures)
  - [Implementation Notes](#implementation-notes)

## Special Forms

The primitive expression types are:
literal, variable, call, lambda, if, set!, quote, and quasiquote.

### set

[(Specification)](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-6.html#TAG:__tex2page_sec_4.1.6)

syntax:

```scheme
(set! <variable> <expression>)
```

`<Expression>` is evaluated, and the resulting value is stored in the location to which `<variable>` is bound. It is an error if `<variable>` is not bound either in some region enclosing the set!​ ​expression or else globally. The result of the set! expression is unspecified.

### if

[(Specification)](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-6.html#TAG:__tex2page_sec_4.1.5)

syntax:

```scheme
(if <test> <consequent> <alternate>) 
(if <test> <consequent>) 
```

An if expression is evaluated as follows: first, `<test>` is evaluated. If it yields a true value, then `<consequent>` is evaluated and its values are returned. Otherwise `<alternate>` is evaluated and its values are returned. If `<test>` yields a false value and no `<alternate>` is specified, then the result of the expression is unspecified.

### define

[(Specification)](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-7.html#TAG:__tex2page_sec_5.3)

There are 3 different forms of `define`:

1. `(define <variable> <expression>)`

2. `(define (<variable> <formals>) <body>)`

`<Formals>` are either a sequence of zero or more variables, or a sequence of one or more variables followed by a space-delimited period and another variable (as in a lambda expression). This form is equivalent to

```scheme
(define <variable>
  (lambda (<formals>) <body>))
```

3. `(define (<variable> .​ ​<formal>) <body>)`

`<Formal>` is a single variable. This form is equivalent to

```scheme
(define <variable>
  (lambda <formal> <body>))
  ```

`(define <variable> <expression>)` has essentially the same effect as the assignment expression `(set!​ ​<variable> <expression>)` if `<variable>` is bound to a non-syntax value. However, if `<variable>` is not bound, or is a syntactic keyword, then the definition will bind `<variable>` to a new location before performing the assignment, whereas it would be an error to perform a set!​ ​on an unboundvariable.

Definitions can occur at the beginning of a `<body>` (that is, the body of a lambda, let, let*, letrec, letrec*, let-values, let*-values, let-syntax, letrec-syntax, parameterize, guard, or case-lambda). Note that such a body might not be apparent until after expansion of other syntax. Such definitions are known as internal definitionsas opposed to the global definitions described above. The variables defined by internal definitions are local to the `<body>`. That is, `<variable>` is bound rather than assigned, and the region of the binding is the entire `<body>`.

### begin

[(Specification)](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-6.html#TAG:__tex2page_sec_4.2.3)

There are 2 different constructs named `begin`

syntax:

```scheme
(begin <expression or definition> …)
```

This form of begin can appear as part of a `<body>`, or at the outermost level of a `<program>`, or at the REPL, or directly nested in a begin that is itself of this form. It causes the contained expressions and definitions to be evaluated exactly as if the enclosing begin construct were not present. This form is commonly used in the output of macros which need to generate multiple definitions and splice them into the context in which they are expanded.

syntax:

```scheme
(begin <expression1> <expression2> …) 
```

This form of begin can be used as an ordinary expression. The `<expression>`s are evaluated sequentially from left to right, and the values of the last `<expression>` are returned. This expression type is used to sequence side effects such as assignments or input and output.

### let

[(Specification)](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-6.html#TAG:__tex2page_sec_4.2.2)

syntax:

```scheme
(let <bindings> <body>) 
```

`<Bindings>` has the form `((<variable1> <init1>) …)`,where each `<init>` is an expression, and `<body>` is a sequence of zero or more definitions followed by a sequence of one or more expressions. It is an error for a `<variable>` to appear more than once in the list of variables being bound.

The `<init>`s are evaluated in the current environment (in some unspecified order), the `<variable>`s are bound to fresh locations holding the results, the `<body>` is evaluated in the extended environment, and the values of the last expression of `<body>` are returned. Each binding of a `<variable>` has `<body>` as its region.

### letrec

[(Specification)](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-6.html#TAG:__tex2page_sec_4.2.2)

syntax:

```scheme
(letrec <bindings> <body>)
```

`<Bindings>` has the form `((<variable1> <init1>) …)`,where each `<init>` is an expression, and `<body>` is a sequence of zero or more definitions followed by a sequence of one or more expressions. It is an error for a `<variable>` to appear more than once in the list of variables being bound.

The `<variable>`s are bound to fresh locations holding unspecified values, the `<init>`s are evaluated in the resulting environment (in some unspecified order), each `<variable>` is assigned to the result of the corresponding `<init>`, the `<body>` is evaluated in the resulting environment, and the values of the last expression in `<body>` are returned. Each binding of a `<variable>` has the entire letrec expression as its region, making it possible to define mutually recursive procedures.

### lambda

[(Specification)](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-6.html#TAG:__tex2page_sec_4.1.4)

syntax:

```scheme
(lambda <formals> <body>)
```

`<body>` is a sequence of zero or more definitions followed by one or more expressions, `<Formals>` has one of the following forms:

- `(<variable1> …)`: The procedure takes a fixed number of arguments; when the procedure is called, the arguments will be stored in fresh locations that are bound to the corresponding variables.

- `<variable>`: The procedure takes any number of arguments; when the procedure is called, the sequence of actual arguments is converted into a newly allocated list, and the list is stored in a fresh location that is bound to `<variable>`.

- `(<variable1> … <variablen>​ ​. <variablen+1>)`: If a space-delimited period precedes the last variable, then the procedure takes n or more arguments, where n is the number of formal arguments before the period (it is an error if there is not at least one). The value stored in the binding of the last variable will be a newly allocated list of the actual arguments left over after all the other actual arguments have been matched up against the other formal arguments.

It is an error for a `<variable>` to appear more than once in `<formals>`.

A lambda expression evaluates to a procedure. The environment in effect when the lambda expression was evaluated is remembered as part of the procedure. When the procedure is later called with some actual arguments, the environment in which the lambda expression was evaluated will be extended by binding the variables in the formal argument list to fresh locations, and the corresponding actual argument values will be stored in those locations. (A fresh location is one that is distinct from every previously existing location.) Next, the expressions in the body of the lambda expression (which, if it contains definitions, represents a letrec* form) will be evaluated sequentially in the extended environment. The results of the last expression in the body will be returned as the results of the procedure call.

### quote

[(Specification)](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-6.html#TAG:__tex2page_sec_4.1.2)

```scheme
(quote <datum>) 
'<datum>
```

`(quote <datum>)` evaluates to `<datum>`

### quasiquote

[(Specification)](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-6.html#TAG:__tex2page_sec_4.2.8)

syntax:

```scheme
(quasiquote <qq template>) 
`<qq template> 
```

auxiliary-syntax:

```scheme
unquote 
,
unquote-splicing 
,﹫
```

“Quasiquote” expressions are useful for constructing a list or vector structure when some but not all of the desired structure is known in advance. If no commasappear within the `<qq template>`, the result of evaluating ``` `<qq template>``` is equivalent to the result of evaluating `'<qq template>`. If a comma appears within the `<qq template>`, however, the expression following the comma is evaluated (“unquoted”) and its result is inserted into the structure instead of the comma and the expression. If a comma appears followed without intervening whitespace by a commercial at-sign (`@`),then it is an error if the following expression does not evaluate to a list; the opening and closing parentheses of the list are then “stripped away” and the elements of the list are inserted in place of the comma at-sign expression sequence. A comma at-sign normally appears only within a list or vector `<qq template>`.

## Procedures

- Arithmetic:
  - `+`
  - `-`
  - `*`
  - `/`
  - `<`
  - `>`
  - `=`
- Booleans
  - `not`
- Types
  - `pair?`
  - `null?`
  - `boolean?`
  - `number?`
  - `string?`
  - `symbol?`
- Equivalence
  - `eq?`
  - `eqv?`
- Lists
  - `cons`
  - `car`
  - `cdr`
  - `list`
  - `append`
  - `length`
  - `reverse`
- Control flow
  - `dynamic-wind`
  - `call/cc`
  - `raise`
  - `raise-continuable`
  - `with-exception-handler`
- `eval`
- `apply`

## Implementation Notes
