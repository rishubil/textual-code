; Source: https://github.com/alemuller/tree-sitter-make
; License: MIT
; Copyright (c) 2022 alemuller

[
 "("
 ")"
 "{"
 "}"
] @punctuation.bracket

[
 ":"
 "&:"
 "::"
 "|"
 ";"
 "\""
 "'"
 ","
] @punctuation.delimiter

[
 "$"
 "$$"
] @punctuation.special

(automatic_variable
 [ "@" "%" "<" "?" "^" "+" "/" "*" "D" "F"] @punctuation.special)

(automatic_variable
 "/" @error . ["D" "F"])

[
 "="
 ":="
 "::="
 "?="
 "+="
 "!="
 "@"
 "-"
 "+"
] @operator

[
 (text)
 (string)
 (raw_text)
] @string

(variable_assignment (word) @string)

[
 "ifeq"
 "ifneq"
 "ifdef"
 "ifndef"
 "else"
 "endif"
 "if"
 "or"
 "and"
] @conditional

"foreach" @repeat

[
 "define"
 "endef"
 "vpath"
 "undefine"
 "export"
 "unexport"
 "override"
 "private"
] @keyword

[
 "include"
 "sinclude"
 "-include"
] @include

[
 "subst" "patsubst" "strip" "findstring" "filter" "filter-out" "sort"
 "word" "words" "wordlist" "firstword" "lastword" "dir" "notdir"
 "suffix" "basename" "addsuffix" "addprefix" "join" "wildcard"
 "realpath" "abspath" "call" "eval" "file" "value" "shell"
] @keyword.function

[
 "error"
 "warning"
 "info"
] @exception

(variable_assignment name: (word) @constant)
(variable_reference (word) @constant)
(comment) @comment

((word) @clean @string.regex
 (#match? @clean "[%\\*\\?]"))

(function_call function: "error" (arguments (text) @text.danger))
(function_call function: "warning" (arguments (text) @text.warning))
(function_call function: "info" (arguments (text) @text.note))

["VPATH" ".RECIPEPREFIX"] @constant.builtin
