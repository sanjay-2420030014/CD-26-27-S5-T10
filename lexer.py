"""
lexer.py - Lexical analyzer (scanner) for a subset of the C language.

How it works
------------
The Lexer reads the source text ONE CHARACTER AT A TIME (peek / advance).
At the start of every lexeme it looks at the first character and decides
which scanning routine to run:

    letter or '_'      -> identifier / keyword
    digit, or '.digit' -> numeric constant
    "                  -> string literal
    '                  -> character literal
    // or /*           -> comment
    # (start of line)  -> preprocessor directive
    operator character -> operator (longest match, e.g. '<<=' before '<<' before '<')
    ( ) { } [ ] ; , .  : -> delimiter
    anything else      -> lexical error (invalid character)

Whitespace is skipped, but line and column numbers are still maintained
(lines and columns both start at 1; a tab counts as one column).

Regular expressions are used only for small VALIDATION checks (numeric
suffixes, character-literal bodies).  The scanning itself is a hand-written
scanner; it is NOT a generic DFA engine.  The identifier and integer loops
follow the state diagrams shown in the web application.
"""

import time
from dataclasses import dataclass, asdict
import re

# --------------------------------------------------------------------------
# Token type names
# --------------------------------------------------------------------------
KEYWORD = "KEYWORD"
IDENTIFIER = "IDENTIFIER"
OPERATOR = "OPERATOR"
CONSTANT = "CONSTANT"
STRING_LITERAL = "STRING_LITERAL"
CHAR_LITERAL = "CHAR_LITERAL"
DELIMITER = "DELIMITER"
COMMENT = "COMMENT"
PREPROCESSOR = "PREPROCESSOR"

TOKEN_TYPES = (KEYWORD, IDENTIFIER, OPERATOR, CONSTANT, STRING_LITERAL,
               CHAR_LITERAL, DELIMITER, COMMENT, PREPROCESSOR)

# --------------------------------------------------------------------------
# Lexical rules
# --------------------------------------------------------------------------
KEYWORDS = frozenset({
    "int", "float", "double", "char", "void", "if", "else", "while", "for",
    "do", "return", "break", "continue", "switch", "case", "default",
    "struct", "const", "static", "sizeof", "typedef", "enum", "union",
    "long", "short", "signed", "unsigned", "extern", "register",
    "volatile", "goto",
})

# Operators grouped by length so that the LONGEST match can be tried first.
OPERATORS_3 = frozenset({"<<=", ">>="})
OPERATORS_2 = frozenset({
    "==", "!=", "<=", ">=", "&&", "||", "++", "--",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<", ">>", "->",
})
OPERATORS_1 = frozenset("+-*/%=<>!&|^~?")

DELIMITERS_1 = frozenset("(){}[];,.:")
ELLIPSIS = "..."          # variadic marker, treated as one DELIMITER

WHITESPACE = frozenset(" \t\r\f\v")
SIGNS = frozenset("+-")
EXPONENT_MARKS = frozenset("eE")
HEX_MARKS = frozenset("xX")

# Validation patterns (regular expressions)
INT_SUFFIX_RE = re.compile(r"(?:[uU](?:ll|LL|[lL])?|(?:ll|LL|[lL])[uU]?)?")
FLOAT_SUFFIX_RE = re.compile(r"[fFlL]?")
CHAR_BODY_RE = re.compile(r"[^\\']|\\(?:[abfnrtv\\'\"?]|x[0-9A-Fa-f]+|[0-7]{1,3})")
INCOMPLETE_EXPONENT_RE = re.compile(r"[eE][+-]?")

MAX_ERROR_LEXEME = 40     # long error lexemes are shortened for display


# --------------------------------------------------------------------------
# Character classes (ASCII only, as in C)
# --------------------------------------------------------------------------
def is_letter(ch):
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z")


def is_digit(ch):
    return "0" <= ch <= "9"


def is_hex_digit(ch):
    return is_digit(ch) or ("a" <= ch <= "f") or ("A" <= ch <= "F")


def is_id_start(ch):
    return is_letter(ch) or ch == "_"


def is_id_part(ch):
    return is_letter(ch) or is_digit(ch) or ch == "_"


# --------------------------------------------------------------------------
# Result records
# --------------------------------------------------------------------------
@dataclass
class Token:
    lexeme: str
    type: str
    line: int
    column: int


@dataclass
class LexError:
    kind: str        # short code, e.g. INVALID_CHARACTER
    message: str
    lexeme: str
    line: int
    column: int


# --------------------------------------------------------------------------
# The scanner
# --------------------------------------------------------------------------
class Lexer:
    """Scans a source string and produces tokens and lexical errors."""

    def __init__(self, source):
        # Windows line endings (\r\n) are normalised to \n so line
        # counting is identical on every platform.
        self.src = source.replace("\r\n", "\n")
        self.pos = 0
        self.line = 1
        self.col = 1
        self.at_line_start = True     # only whitespace seen so far on this line
        self.tokens = []
        self.errors = []

    # ---- low level character access --------------------------------------
    def peek(self, offset=0):
        """Return the character `offset` places ahead, or '' at end of input."""
        index = self.pos + offset
        return self.src[index] if index < len(self.src) else ""

    def advance(self):
        """Consume one character and update the line / column counters."""
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def at_end(self):
        return self.pos >= len(self.src)

    # ---- result helpers ----------------------------------------------------
    def emit(self, token_type, lexeme, line, col):
        self.tokens.append(Token(lexeme, token_type, line, col))

    def error(self, kind, message, lexeme, line, col):
        lexeme = lexeme.split("\n")[0]       # show only the first line
        if len(lexeme) > MAX_ERROR_LEXEME:
            lexeme = lexeme[:MAX_ERROR_LEXEME] + "..."
        self.errors.append(LexError(kind, message, lexeme, line, col))

    # ---- main loop ---------------------------------------------------------
    def tokenize(self):
        """Scan the whole input. Returns (tokens, errors)."""
        while not self.at_end():
            ch = self.peek()

            if ch == "\n":
                self.advance()
                self.at_line_start = True
                continue
            if ch in WHITESPACE:
                self.advance()
                continue

            line, col = self.line, self.col
            starts_line = self.at_line_start
            self.at_line_start = False

            if ch == "#" and starts_line:
                self.scan_preprocessor(line, col)
            elif ch == "/" and self.peek(1) == "/":
                self.scan_line_comment(line, col)
            elif ch == "/" and self.peek(1) == "*":
                self.scan_block_comment(line, col)
            elif is_id_start(ch):
                self.scan_identifier(line, col)
            elif is_digit(ch) or (ch == "." and is_digit(self.peek(1))):
                self.scan_number(line, col)
            elif ch == '"':
                self.scan_string(line, col)
            elif ch == "'":
                self.scan_char(line, col)
            elif self.scan_operator_or_delimiter(line, col):
                pass
            else:
                self.scan_invalid_character(line, col)

        return self.tokens, self.errors

    # ---- identifiers and keywords -----------------------------------------
    def scan_identifier(self, line, col):
        # letter/_  followed by any number of letters, digits, '_'
        start = self.pos
        while is_id_part(self.peek()):
            self.advance()
        lexeme = self.src[start:self.pos]
        self.emit(KEYWORD if lexeme in KEYWORDS else IDENTIFIER, lexeme, line, col)

    # ---- numeric constants --------------------------------------------------
    def scan_number(self, line, col):
        """Integer, floating-point, exponential and hexadecimal constants.

        After the number itself, any directly attached letters/digits are
        read too.  They must form a valid suffix (u, l, ul, f ...); otherwise
        the whole lexeme is reported as an error.
        """
        start = self.pos
        is_hex = False
        is_float = False
        hex_digits = 0

        if self.peek() == "0" and self.peek(1) in HEX_MARKS:
            is_hex = True
            self.advance()
            self.advance()
            while is_hex_digit(self.peek()):
                self.advance()
                hex_digits += 1
        else:
            while is_digit(self.peek()):
                self.advance()
            if self.peek() == ".":
                is_float = True
                self.advance()
                while is_digit(self.peek()):
                    self.advance()
            # exponent: e/E, optional sign, at least one digit
            if self.peek() in EXPONENT_MARKS:
                sign_len = 1 if self.peek(1) in SIGNS else 0
                if is_digit(self.peek(1 + sign_len)):
                    is_float = True
                    for _ in range(1 + sign_len):
                        self.advance()
                    while is_digit(self.peek()):
                        self.advance()

        number_end = self.pos

        # Read anything glued to the number: letters, digits, '_', or a second
        # '.' followed by a digit (as in 1.2.3).
        while True:
            ch = self.peek()
            if is_id_part(ch) or (ch == "." and is_digit(self.peek(1))):
                self.advance()
                # keep an exponent sign with its 'e', e.g. the '+' in 1e+
                if (not is_hex and ch in EXPONENT_MARKS
                        and self.peek() in SIGNS and not is_digit(self.peek(1))):
                    self.advance()
            else:
                break

        lexeme = self.src[start:self.pos]
        suffix = self.src[number_end:self.pos]

        if is_hex:
            valid = hex_digits > 0 and INT_SUFFIX_RE.fullmatch(suffix) is not None
        elif is_float:
            valid = FLOAT_SUFFIX_RE.fullmatch(suffix) is not None
        else:
            valid = INT_SUFFIX_RE.fullmatch(suffix) is not None

        if valid:
            self.emit(CONSTANT, lexeme, line, col)
        elif (not is_hex and not is_float and suffix
              and is_id_start(suffix[0])
              and INCOMPLETE_EXPONENT_RE.fullmatch(suffix) is None
              and all(is_id_part(c) for c in suffix)):
            # e.g. 2count : digits followed directly by a name
            self.error("INVALID_IDENTIFIER",
                       f"Invalid identifier '{lexeme}': an identifier cannot start with a digit",
                       lexeme, line, col)
        else:
            self.error("MALFORMED_NUMBER",
                       f"Malformed numeric literal '{lexeme}'",
                       lexeme, line, col)

    # ---- string literals ----------------------------------------------------
    def scan_string(self, line, col):
        start = self.pos
        self.advance()                       # opening "
        while True:
            ch = self.peek()
            if ch == "" or ch == "\n":
                self.error("UNTERMINATED_STRING",
                           "Unterminated string literal (missing closing \")",
                           self.src[start:self.pos], line, col)
                return
            self.advance()
            if ch == "\\" and self.peek() != "":
                self.advance()               # escaped character, e.g. \" or \n
            elif ch == '"':
                self.emit(STRING_LITERAL, self.src[start:self.pos], line, col)
                return

    # ---- character literals -------------------------------------------------
    def scan_char(self, line, col):
        start = self.pos
        self.advance()                       # opening '
        while True:
            ch = self.peek()
            if ch == "" or ch == "\n":
                self.error("UNTERMINATED_CHAR",
                           "Unterminated character literal (missing closing ')",
                           self.src[start:self.pos], line, col)
                return
            self.advance()
            if ch == "\\" and self.peek() not in ("", "\n"):
                self.advance()
            elif ch == "'":
                break

        lexeme = self.src[start:self.pos]
        body = lexeme[1:-1]
        if body == "":
            self.error("EMPTY_CHAR", "Empty character literal", lexeme, line, col)
        elif CHAR_BODY_RE.fullmatch(body):
            self.emit(CHAR_LITERAL, lexeme, line, col)
        else:
            self.error("INVALID_CHAR_LITERAL",
                       "Invalid character literal (must contain exactly one character)",
                       lexeme, line, col)

    # ---- comments -----------------------------------------------------------
    def scan_line_comment(self, line, col):
        start = self.pos
        while self.peek() not in ("", "\n"):
            self.advance()
        self.emit(COMMENT, self.src[start:self.pos], line, col)

    def scan_block_comment(self, line, col):
        start = self.pos
        self.advance()
        self.advance()                       # consume '/*'
        while not self.at_end():
            if self.peek() == "*" and self.peek(1) == "/":
                self.advance()
                self.advance()
                self.emit(COMMENT, self.src[start:self.pos], line, col)
                return
            self.advance()
        self.error("UNTERMINATED_COMMENT",
                   "Unterminated block comment (missing */)",
                   self.src[start:self.pos], line, col)

    # ---- preprocessor -------------------------------------------------------
    def scan_preprocessor(self, line, col):
        """A '#' that is the first non-blank character of a line starts a
        directive such as #include or #define; the whole line is one token
        (a trailing backslash continues the directive on the next line)."""
        start = self.pos
        while not self.at_end():
            if self.peek() == "\\" and self.peek(1) == "\n":
                self.advance()
                self.advance()
            elif self.peek() == "\n":
                break
            else:
                self.advance()
        self.emit(PREPROCESSOR, self.src[start:self.pos].rstrip(), line, col)

    # ---- operators and delimiters -------------------------------------------
    def scan_operator_or_delimiter(self, line, col):
        """Longest-match recognition. Returns True if something was consumed."""
        three = self.src[self.pos:self.pos + 3]
        two = self.src[self.pos:self.pos + 2]
        one = self.peek()

        if three in OPERATORS_3:
            return self._take(OPERATOR, 3, line, col)
        if three == ELLIPSIS:
            return self._take(DELIMITER, 3, line, col)
        if two in OPERATORS_2:
            return self._take(OPERATOR, 2, line, col)
        if one in OPERATORS_1:
            return self._take(OPERATOR, 1, line, col)
        if one in DELIMITERS_1:
            return self._take(DELIMITER, 1, line, col)
        return False

    def _take(self, token_type, length, line, col):
        start = self.pos
        for _ in range(length):
            self.advance()
        self.emit(token_type, self.src[start:self.pos], line, col)
        return True

    # ---- invalid characters -------------------------------------------------
    def scan_invalid_character(self, line, col):
        ch = self.advance()
        shown = ch if ch.isprintable() else repr(ch)
        if ch == "#":
            message = "Invalid character '#' (a preprocessor directive must start a line)"
        else:
            message = f"Invalid character '{shown}'"
        self.error("INVALID_CHARACTER", message, shown, line, col)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def tokenize(source):
    """Scan `source`; returns (list[Token], list[LexError])."""
    return Lexer(source).tokenize()


def compute_statistics(tokens, errors):
    """Statistics that are derived directly from the token and error lists."""
    by_type = {t: 0 for t in TOKEN_TYPES}
    for token in tokens:
        by_type[token.type] += 1
    by_error = {}
    for err in errors:
        by_error[err.kind] = by_error.get(err.kind, 0) + 1
    return {
        "total_tokens": len(tokens),
        "keywords": by_type[KEYWORD],
        "identifiers": by_type[IDENTIFIER],
        "operators": by_type[OPERATOR],
        "constants": by_type[CONSTANT],
        "string_literals": by_type[STRING_LITERAL],
        "char_literals": by_type[CHAR_LITERAL],
        "delimiters": by_type[DELIMITER],
        "comments": by_type[COMMENT],
        "preprocessor": by_type[PREPROCESSOR],
        "errors": len(errors),
        "by_type": by_type,
        "errors_by_kind": by_error,
    }


def line_information(source, tokens, errors):
    """Per-line summary: the source text, tokens that start on the line and
    errors reported on it."""
    lines = source.replace("\r\n", "\n").split("\n")
    info = [{"line": i + 1, "text": text, "tokens": 0, "errors": 0}
            for i, text in enumerate(lines)]
    for token in tokens:
        info[token.line - 1]["tokens"] += 1
    for err in errors:
        info[err.line - 1]["errors"] += 1
    return info


def analyze(source):
    """Run the lexer and return everything the web page needs."""
    started = time.perf_counter()
    tokens, errors = tokenize(source)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    stats = compute_statistics(tokens, errors)
    lines = line_information(source, tokens, errors)
    return {
        "tokens": [asdict(t) for t in tokens],
        "errors": [asdict(e) for e in errors],
        "stats": stats,
        "lines": lines,
        "summary": {
            "lines": len(lines),
            "characters": len(source),
            "elapsed_ms": elapsed_ms,
            "status": "success" if not errors else "errors",
        },
    }
