; Source: https://github.com/fwcd/tree-sitter-kotlin
; License: MIT
; Copyright (c) 2020 fwcd

;;; Identifiers

(simple_identifier) @variable

; `it` keyword inside lambdas
((simple_identifier) @variable.builtin
(#eq? @variable.builtin "it"))

; `field` keyword inside property getter/setter
((simple_identifier) @variable.builtin
(#eq? @variable.builtin "field"))

; `this` this keyword inside classes
(this_expression) @variable.builtin

; `super` keyword inside classes
(super_expression) @variable.builtin

(class_parameter
	(simple_identifier) @property)

(class_body
	(property_declaration
		(variable_declaration
			(simple_identifier) @property)))

; id_1.id_2.id_3: `id_2` and `id_3` are assumed as object properties
(_
	(navigation_suffix
		(simple_identifier) @property))

(enum_entry
	(simple_identifier) @constant)

(type_identifier) @type

((type_identifier) @type.builtin
	(#any-of? @type.builtin
		"Byte" "Short" "Int" "Long" "UByte" "UShort" "UInt" "ULong"
		"Float" "Double" "Boolean" "Char" "String"
		"Array" "ByteArray" "ShortArray" "IntArray" "LongArray"
		"UByteArray" "UShortArray" "UIntArray" "ULongArray"
		"FloatArray" "DoubleArray" "BooleanArray" "CharArray"
		"Map" "Set" "List" "EmptyMap" "EmptySet" "EmptyList"
		"MutableMap" "MutableSet" "MutableList"
))

(package_header
	. (identifier)) @namespace

(import_header
	"import" @include)

(label) @label

;;; Function definitions

(function_declaration
	. (simple_identifier) @function)

(getter ("get") @function.builtin)
(setter ("set") @function.builtin)

(primary_constructor) @constructor
(secondary_constructor ("constructor") @constructor)

(constructor_invocation
	(user_type (type_identifier) @constructor))

(anonymous_initializer ("init") @constructor)

(parameter (simple_identifier) @parameter)
(parameter_with_optional_type (simple_identifier) @parameter)

(lambda_literal
	(lambda_parameters
		(variable_declaration (simple_identifier) @parameter)))

;;; Function calls

(call_expression . (simple_identifier) @function)

(call_expression
	(navigation_expression
		(navigation_suffix (simple_identifier) @function) . ))

(call_expression
	. (simple_identifier) @function.builtin
    (#any-of? @function.builtin
		"arrayOf" "arrayOfNulls" "byteArrayOf" "shortArrayOf" "intArrayOf"
		"longArrayOf" "ubyteArrayOf" "ushortArrayOf" "uintArrayOf" "ulongArrayOf"
		"floatArrayOf" "doubleArrayOf" "booleanArrayOf" "charArrayOf" "emptyArray"
		"mapOf" "setOf" "listOf" "emptyMap" "emptySet" "emptyList"
		"mutableMapOf" "mutableSetOf" "mutableListOf"
		"print" "println" "error" "TODO" "run" "runCatching" "repeat"
		"lazy" "lazyOf" "enumValues" "enumValueOf"
		"assert" "check" "checkNotNull" "require" "requireNotNull"
		"with" "synchronized"
))

;;; Literals

[
	(line_comment)
	(multiline_comment)
	(shebang_line)
] @comment

(real_literal) @float
[
	(integer_literal)
	(long_literal)
	(hex_literal)
	(bin_literal)
	(unsigned_literal)
] @number

[
	(null_literal)
	(boolean_literal)
] @boolean

(character_literal) @character
(string_literal) @string
(character_escape_seq) @string.escape

;;; Keywords

(type_alias "typealias" @keyword)
[
	(class_modifier)
	(member_modifier)
	(function_modifier)
	(property_modifier)
	(platform_modifier)
	(variance_modifier)
	(parameter_modifier)
	(visibility_modifier)
	(reification_modifier)
	(inheritance_modifier)
] @keyword

[
	"val" "var" "enum" "class" "object" "interface"
] @keyword

("fun") @keyword.function

(jump_expression) @keyword.return

[
	"if" "else" "when"
] @conditional

[
	"for" "do" "while"
] @repeat

[
	"try" "catch" "throw" "finally"
] @exception

(annotation
	"@" @attribute (use_site_target)? @attribute)
(annotation
	(user_type (type_identifier) @attribute))
(annotation
	(constructor_invocation (user_type (type_identifier) @attribute)))

(file_annotation
	"@" @attribute "file" @attribute ":" @attribute)
(file_annotation
	(user_type (type_identifier) @attribute))
(file_annotation
	(constructor_invocation (user_type (type_identifier) @attribute)))

;;; Operators & Punctuation

[
	"!" "!=" "!==" "=" "==" "===" ">" ">=" "<" "<="
	"||" "&&" "+" "++" "+=" "-" "--" "-=" "*" "*=" "/" "/=" "%" "%="
	"?." "?:" "!!" "is" "in" "as" "as?" ".." "->"
] @operator

[
	"(" ")" "[" "]" "{" "}"
] @punctuation.bracket

[
	"." "," ";" ":" "::"
] @punctuation.delimiter

(string_literal
	"$" @punctuation.special
	(interpolated_identifier) @none)
(string_literal
	"${" @punctuation.special
	(interpolated_expression) @none
	"}" @punctuation.special)
