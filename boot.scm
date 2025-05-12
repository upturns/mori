
;; Boostrapping utils
(define (and2 x y)
    (if x
        (if y
            #t
            #f)
        #f))


(define (map-single proc lst)
    (if (null? lst)
        '()
        (cons (proc (car lst)) (map-single proc (cdr lst)))))


(define (map-multi proc lists)
    (if (ormap null? lists)
        ;; if any of the lists are empty, exit
        '()
        ;; otherwise, take the first element from every list
        (let ((fsts (map car lists)))
            (cons (apply proc fsts) (map-multi proc (map cdr lists))))))


(define (map proc . list-args)
    (if (null? list-args)
        '()
        (if (eq? 1 (length list-args))
            ;; 'JUST-MAP-PROC-OVER-args
            (map-single proc (car list-args))
            ;; todo: raise an error if the maps are not the same length
            (map-multi proc list-args))))


(define (ormap pred lst)
  (if (null? lst)
    #f
    (if (pred (car lst))
        #t
        (ormap pred (cdr lst)))))


(define (fold-right f init lst)
  (if (null? lst)
      init
      (f (car lst) (fold-right f init (cdr lst)))))


(define (is-ellipsis-pair p)
    (if (pair? p)
        (if (pair? (cdr p))
            (if (eq? '... (cadr p))
                #t
                #f)
            #f)
        #f))

;; Standard built-ins
(define (cadr exp)
    (car (cdr exp)))

(define (cddr exp)
    (cdr (cdr exp)))

(define (assq var alist)
    (begin
        (if (null? alist)
            #f
            (let ((aitem (car alist)))
                (if (eq? (car aitem) var)
                    aitem
                    (assq var (cdr alist)))))))


(define (snoc lst elem)
  (append lst (list elem)))


;; sk = success continuation
;; fk = failure continuation
(define (match p e sk fk)
  (if (and2 (pair? p) (pair? e))
    (match* (car p) (car e)
            (lambda (b)
                (match* (cdr p) (cdr e)
                        (lambda (b2) (sk (append b b2)))
                        fk))
            fk)
    (if (eq? p '_)
        (sk '())
        (if (symbol? p)
            (sk (list (cons p e)))
            (if (null? p)
                (if (null? e)
                    (sk '())
                    (fk))
                (fk))))))


(define (match* p e sk fk)
    (if (is-ellipsis-pair p)
        ;; 'A
        (letrec ((loop (lambda (e b)
                            (if (null? e)
                                (match* (cddr p) e
                                        (lambda (b^) (sk (cons (cons '... b) b^)))
                                        ;; (lambda (b^) (sk `((... . ,b) . ,b^)))
                                        fk)
                                (match* (car p) (car e)
                                        (lambda (b^)
                                            (loop (cdr e) (snoc b b^)))
                                        (lambda ()
                                            (match* (cddr p) e
                                                    (lambda (b^) (sk (cons (cons '... b) b^)))
                                                    fk)))))))
                (loop e '()))
        (match p e sk fk)))


(define (extract-... p bindings)
  (if (null? bindings)
      '()
      (let ((rest (extract-... p (cdr bindings)))
            (b (car bindings)))
        (if (and2 (eq? (car b) '...) (not (null? (cdr b))))
            (let ((names (map car (cadr b))))
              (if (ormap (lambda (x) (mem* x p)) names)
                  (cons (cdr b) rest)
                  rest))
            rest))))


;; determines whether a variable is relevant to a pattern.
(define (mem* x ls)
  (if (is-ellipsis-pair ls)
    #f
    (if (pair? ls)
        ;; (or (mem* x (car ls)) (mem* x (cdr ls)))
        (let ((fst-match (mem* x (car ls))))
            (if fst-match
                fst-match
                (mem* x (cdr ls))))
        (eq? x ls))))


(define (instantiate p bindings)
    (if (pair? p)
        (cons (instantiate* (car p) bindings)
              (instantiate* (cdr p) bindings))
        (let ((bound-val (assq p bindings)))
            (if bound-val
                (cdr bound-val)
                p))))


(define (instantiate* p bindings)
  (begin
    ; (display "INSTANTIATING")
    ; (newline)
    ; (display p)
    ; (newline)
    (if (is-ellipsis-pair p)
        (let ((bindings... (extract-... (car p) bindings)))
            (if (null? bindings...)
                (instantiate* (cddr p) bindings)
                (append
                    ;; THE PROBLEM IS HERE
                    (apply map (cons (lambda b*
                                         (instantiate* (car p)
                                                       (append (apply append b*)
                                                        bindings)))
                                    bindings...))
                    (instantiate* (cddr p) bindings))))
        (instantiate p bindings))))


;; (display (instantiate* '(let ((x e) ...) b)
;;                 '((... ((x . x) (e . 5)) ((x . y) (e . 6))) (b + x y))))

;; (display (instantiate* '((a b ...) ...)
;;                  '((... ((a . 1)) ((a . 2)) ((a . 3)))
;;                    (... ((b . x)) ((b . y))))))

; (pretty-print (instantiate* '((a a ...) ...) '((... ((a . 1)) ((a . 2)) ((a . 3))))))

;; a syntax rule is an alist of cases

(define rule '(
                ((_ e) . e)
                ((_ e e* ...) . (let ((t e)) (if t t (my-or e* ...))))))

(define rules (list rule))

(define (apply-rule cases exp)
    (if (null? cases)
        'FAIL
        (if (not (pair? exp))
            'FAIL
            (let ((fst-case (car cases)))
                (if (eq? (car exp) 'my-or)
                    (let ((m (match* (car fst-case) exp (lambda (x) x) (lambda () 'FAIL))))
                        (if (eq? m 'FAIL)
                            (apply-rule (cdr cases) exp)
                            (instantiate* (cdr fst-case) m)))
                    (apply-rule (cdr cases) exp))))))


(define (apply-all-rules rules exp)
    (if (null? rules)
        'FAIL
        (let ((expanded (apply-rule (car rules) exp)))
            (if (eq? expanded 'FAIL)
                ; (apply-all-rules (cdr rules) exp)
                'FAIL
                expanded))))



(define (expand exp)
    (if (pair? exp)
        (let ((mapped (apply-all-rules rules exp)))
            (if (eq? mapped 'FAIL)
                ; (expand (cdr expr))
                (cons (expand (car exp)) (expand (cdr exp)))
                (expand mapped)))
                ; mapped
        exp))
                

; (define (expand exp)
;     (if (null? exp)
;         exp
;         (if (atom? exp)
;             exp
;             ; should be a pair
;             (let ((mapped (apply-all-rules rules exp)))
;                 (if (eq? mapped 'FAIL)
;                     (cons (expand (car expr)) (expand (cdr expr)))
;                     (expand mapped))))))
;                     ; mapped


(define (repl-iteration)
    (begin
        (display "> ")
        (let ((input (read)))
            (let ((result (eval input)))
                (display result)))
        ; (display (eval (read)))
        (newline)
        (repl-iteration)))


(display "Mori Scheme v0.1")
(newline)
(display "Enter `(help)` for more information.")
(newline)
(with-exception-handler
    (lambda (x)
        (display "!! Err: ")
        (display x)
        (newline)
        (repl-iteration))
    repl-iteration)
; (newline)

; (define input '(my-or #f #f #t #t))
; ; (pretty-print (expand input))
; ; (pretty-print (apply-all-rules rules input))
; (pretty-print (expand input))
; (pretty-print (apply-rule rule input))

; (let ((m (match* (car rule2) input (lambda (x) x) (lambda () 'FAIL))))
;     ; (pretty-print m))
;     (pretty-print (instantiate* (cdr rule2) m)))
    ; (pretty-print (instantiate* cdr(rule1) m)))
    


;; (display `(a `(b ,(+ 1 2) ,(foo ,(+ 1 3)) d)))
; (display `(1 `(2 ,(+ 1 2) 4)))
;; (display ``A)
