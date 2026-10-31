# LexiScan – Lexical Analyzer

**Design and Implementation of a Lexical Analyzer for Source Code Tokenization**

Subject: Compiler Design · Academic Year: 2026–2027
Project Guide: Dr. P Krishna Kishore

---

## 1. Introduction

Lexical analysis is the first phase of a compiler. It reads the source program as a stream of characters and groups the characters into meaningful units called **lexemes**. Each lexeme is classified into a **token** (keyword, identifier, operator, …) that the next phase, the parser, can work with.

LexiScan is a web application that performs this phase for a subset of the C language. The scanner is written in Python, the web server uses Flask, and the interface is plain HTML, CSS and JavaScript. There is no database and no machine learning.

## 2. Abstract

The project implements a lexical analyzer that accepts C source code, scans it character by character, identifies lexemes with predefined lexical rules and classifies them into keywords, identifiers, operators, constants, string literals, character literals, delimiters, comments and preprocessor lines. The line number and column number of every token are recorded. Common lexical errors (invalid characters, invalid identifiers, malformed numbers, unterminated strings, character literals and block comments) are detected and reported with their position. Token statistics are shown as cards and charts, and the token table can be searched, filtered and exported as CSV.

## 3. Objectives

- Scan source code character by character and identify lexemes.
- Classify lexemes into token categories using longest-match rules.
- Produce a token table with lexeme, token type, line number and column number.
- Detect lexical errors and report message, line, column and the offending lexeme.
- Display token statistics and demonstrate regular expressions and finite automata.

## 4. Technologies Used

| Layer | Technology |
|---|---|
| Lexical analyzer | Python 3 (hand-written character-by-character scanner, `re` module for small validation checks) |
| Web server | Flask |
| Front end | HTML5, CSS3, JavaScript (no framework, no external libraries) |
| Tests | Python `unittest` |

## 5. System Workflow

```
 Browser (index.html + script.js)               Flask (app.py)                 lexer.py
 ───────────────────────────────                ──────────────                 ────────
 user types / loads code
 click "Analyze Code"
 validate not empty ──► POST /api/analyze ──►  validate JSON, type, size
                         {"source": "..."}      call lexer.analyze(source) ──► scan char by char
                                                                               classify lexemes
                                                                               track line / column
                                                                               collect errors
                                                                               compute statistics
 render tables, charts ◄── JSON result ◄─────   return result  ◄───────────── tokens, errors, stats, lines
```

All results are generated from the entered code; nothing is hard-coded.

## 6. Token Categories

| Token type | Description | Examples |
|---|---|---|
| `KEYWORD` | The 31 C keywords listed in the project specification | `int`, `while`, `return` |
| `IDENTIFIER` | Letter or `_`, then letters, digits or `_`; not a keyword | `age`, `total_marks`, `number1` |
| `OPERATOR` | Arithmetic, relational, assignment, logical, increment/decrement, bitwise, `->`, `?` | `==`, `++`, `<<=`, `+` |
| `CONSTANT` | Integer, floating-point, exponential, hexadecimal (with optional `u`/`l`/`f` suffixes) | `10`, `3.14`, `1.5e3`, `0x2A` |
| `STRING_LITERAL` | Text in double quotes, with escape sequences | `"Hello World"` |
| `CHAR_LITERAL` | One character or escape sequence in single quotes | `'A'`, `'5'`, `'\n'` |
| `DELIMITER` | `( ) { } [ ] ; , . :` and `...` | `;` |
| `COMMENT` | `// ...` and `/* ... */` (kept as COMMENT tokens) | `// note` |
| `PREPROCESSOR` | A line whose first non-blank character is `#`; the whole line is one token | `#include <stdio.h>` |

`PREPROCESSOR` is an addition to the categories in the specification. The required sample program contains `#include <stdio.h>`; without this category its `<`, `stdio`, `.` and `h` would be reported as separate operator and identifier tokens, which is not what a C preprocessor line means.

### Lexical errors detected

| Error kind | Example | Reported as |
|---|---|---|
| Invalid character | `@`, `$`, `` ` ``, `\` outside a literal, a `#` that is not at the start of a line | `Invalid character '@'` |
| Invalid identifier | `2count` | identifier cannot start with a digit |
| Malformed numeric literal | `12.5.3`, `0x`, `0xZZ`, `1e`, `3.14abc` | `Malformed numeric literal` |
| Unterminated string | `"Hello World;` | missing closing `"` |
| Unterminated character literal | `'x;` | missing closing `'` |
| Empty / multi-character literal | `''`, `'AB'` | invalid character literal |
| Unterminated block comment | `/* never closed` | missing `*/` |

After an error the scanner keeps going, so several errors can be reported in one run.

## 7. Implementation Details

### Files

```
LexiScan/
├── app.py              Flask server: GET / and POST /api/analyze, input validation
├── lexer.py            The lexical analyzer (scanner, statistics, line information)
├── requirements.txt    Flask
├── README.md
├── templates/index.html
├── static/css/style.css
├── static/js/script.js
├── tests/test_lexer.py 50 automated tests (scanner + Flask API)
└── screenshots/        Screenshots of the running application
```

### How the scanner works (`lexer.py`)

The `Lexer` class holds the source text, the current position and the current line and column. Two small methods give character-by-character access:

- `peek(offset)` looks at a character without consuming it (returns `''` at the end of input).
- `advance()` consumes one character and updates the line/column counters (a newline increments the line and resets the column to 1).

`tokenize()` loops until the input ends. It skips whitespace (still counting lines and columns), remembers where the lexeme starts, and looks at the first character to choose a scanning routine:

| First character | Routine |
|---|---|
| `#` at the start of a line | `scan_preprocessor` |
| `//` or `/*` | `scan_line_comment` / `scan_block_comment` |
| letter or `_` | `scan_identifier` (then keyword-table lookup) |
| digit, or `.` followed by a digit | `scan_number` |
| `"` | `scan_string` |
| `'` | `scan_char` |
| operator / delimiter character | `scan_operator_or_delimiter` |
| anything else | `scan_invalid_character` |

Important points:

- **Longest match.** `scan_operator_or_delimiter` tries a 3-character candidate, then 2 characters, then 1. So `<<=` is one token, `==` is not two `=`, and `a+++b` becomes `a`, `++`, `+`, `b`.
- **Keywords vs identifiers.** An identifier is scanned first; if the lexeme is in the keyword set it becomes a `KEYWORD`.
- **Numbers.** After the number itself, letters and digits glued to it are read too. They must form a valid suffix (checked with a regular expression); otherwise the whole lexeme is reported as one error, so `2count` and `12.5.3` give a single clear message each.
- **Columns.** Lines and columns start at 1. A tab counts as one column. Windows line endings (`\r\n`) are normalised so line numbers are the same on every system.
- **Statistics.** `compute_statistics` counts the token list that was produced, so the statistics always match the token table.

### Regular expressions and finite automata

The **Theory** page of the application lists a regular expression for each token class and shows state-transition diagrams for identifiers (`[A-Za-z_][A-Za-z0-9_]*`) and integers (`[0-9]+`).

These diagrams are **theoretical**. LexiScan does **not** contain a generic DFA engine or a transition table. The scanner is hand-written, and its loops follow the same states: for example `scan_identifier` stays in a loop (`while is_id_part(self.peek())`) exactly as state `q1` loops on letters, digits and `_`. The `re` module is used only to validate numeric suffixes and the body of character literals.

### Web interface

- **Home** – project title, description, *Start Analyzing* button and the latest totals (tokens, keywords, identifiers, errors).
- **Editor** – source area with line numbers, *Load Sample Program*, *Load Error Sample*, *Clear Code*, *Analyze Code*.
- **Results** – tabs: *Summary*, *Tokens* (search, type filter, CSV download), *Statistics* (cards, bar chart, donut chart), *Lexical Errors*, *Line Information*; *Clear Analysis* resets everything.
- **Theory** – regular expressions, automata diagrams, and how they relate to the code.
- **About** – abstract, objectives, technologies, team and guide.

The CSV download contains the tokens currently shown in the table (all tokens when no search/filter is active). A lexeme that starts with `=`, `+`, `-` or `@` is written with a leading `'` so that Excel does not treat it as a formula (for example `=` is saved as `'=`).

### Limits and input handling

- Empty or whitespace-only code is rejected with a message (in the browser and by the server, HTTP 400).
- Non-JSON requests, a missing or non-string `source`: HTTP 400. More than 200,000 characters: HTTP 413.
- Unknown routes and wrong methods return JSON errors (404, 405).
- Lexemes are inserted into the page with `textContent`, never as HTML.
- Tables draw at most 5,000 rows at a time (the CSV contains everything).

## 8. Installation and Execution (Windows)

Requirements: **Python 3.9 or newer** (tested with 3.13) installed and available as `python`.

1. Open the `LexiScan` folder in **VS Code** (*File → Open Folder…*).
2. Open the terminal (*Terminal → New Terminal*).
3. Create a virtual environment:

   ```
   python -m venv venv
   ```

4. Activate it:

   ```
   venv\Scripts\activate
   ```

   In PowerShell, if you see *“running scripts is disabled on this system”*, run this once in the same terminal and activate again:

   ```
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```

   (In *Command Prompt* the plain `venv\Scripts\activate` command works without this.)

5. Install the dependencies:

   ```
   pip install -r requirements.txt
   ```

6. Start the Flask application:

   ```
   python app.py
   ```

7. Open **http://127.0.0.1:5000** in a browser. Stop the server with `Ctrl + C`.

## 9. Testing

With the virtual environment active, run from the project folder:

```
python -m unittest discover -s tests -v
```

The suite (`tests/test_lexer.py`, 50 tests) covers: variable declarations, arithmetic expressions, conditional statements, loops, functions, string and character literals, single-line and multi-line comments, floating-point / exponential / hexadecimal constants, preprocessor lines, longest-match operators, line and column numbers (including tabs and Windows line endings), invalid characters, invalid identifiers, malformed numbers, unterminated strings / characters / comments, that valid code produces no errors, that statistics equal the token table, and the Flask API (valid input, empty input, bad requests, too-large input, wrong method, static files).

Result of the last run in the development environment:

```
Ran 50 tests in 0.1s
OK
```

## 10. Sample Inputs and Outputs

### Sample 1 – valid program (loaded in the editor by default)

```c
#include <stdio.h>

int main() {
    int age = 20;
    float marks = 85.5;

    if (age >= 18) {
        printf("Eligible");
    } else {
        printf("Not Eligible");
    }

    return 0;
}
```

First rows of the token table:

| Lexeme | Token Type | Line | Column |
|---|---|---|---|
| `#include <stdio.h>` | PREPROCESSOR | 1 | 1 |
| `int` | KEYWORD | 3 | 1 |
| `main` | IDENTIFIER | 3 | 5 |
| `(` | DELIMITER | 3 | 9 |
| `)` | DELIMITER | 3 | 10 |
| `{` | DELIMITER | 3 | 12 |
| `int` | KEYWORD | 4 | 5 |
| `age` | IDENTIFIER | 4 | 9 |
| `=` | OPERATOR | 4 | 13 |
| `20` | CONSTANT | 4 | 15 |
| `;` | DELIMITER | 4 | 17 |
| … | … | … | … |
| `>=` | OPERATOR | 7 | 13 |
| `"Eligible"` | STRING_LITERAL | 8 | 16 |

Statistics: **41 tokens** = 6 keywords + 6 identifiers + 3 operators + 4 constants + 2 string literals + 19 delimiters + 1 preprocessor line. **0 errors.**

### Sample 2 – program with lexical errors (*Load Error Sample*)

Reported errors:

| # | Error message | Line | Column | Lexeme |
|---|---|---|---|---|
| 1 | Invalid identifier '2count': an identifier cannot start with a digit | 5 | 9 | `2count` |
| 2 | Malformed numeric literal '12.5.3' | 7 | 19 | `12.5.3` |
| 3 | Invalid character '@' | 9 | 14 | `@` |
| 4 | Invalid character '$' | 9 | 20 | `$` |
| 5 | Invalid character literal (must contain exactly one character) | 11 | 18 | `'AB'` |
| 6 | Unterminated character literal (missing closing ') | 13 | 20 | `'x;` |
| 7 | Unterminated string literal (missing closing ") | 15 | 17 | `"Hello World;` |
| 8 | Unterminated block comment (missing */) | 18 | 1 | `/* this block comment is never closed` |

## 11. Design Notes and Known Limitations

- Only a **subset of C** is supported, as listed in the project specification. C features such as trigraphs, digraphs, wide/prefixed literals (`L"..."`), octal validation (`09` is accepted as an integer), and macro-specific tokens (`#`, `##` inside a macro) are not handled.
- `$` is reported as an invalid character, although some C compilers accept it in identifiers.
- A multi-character literal such as `'AB'` is reported as an error (real C compilers only warn).
- After an unterminated string or character literal, the rest of that line is part of the error lexeme, because the closing quote could not be found.
- Tabs count as one column.

## 12. Project Team

| # | Name | Roll Number |
|---|---|---|
| 1 | V Sanjay Bhaargav | 2420030014 |
| 2 | P Rahul | 2420030368 |
| 3 | Mvs Aasrith | 2420030573 |
| 4 | M Rishikesh | 2420030012 |

Project Guide: **Dr. P Krishna Kishore**
