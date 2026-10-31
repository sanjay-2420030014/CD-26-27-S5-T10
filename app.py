"""
app.py - Flask web server for LexiScan.

Routes
------
GET  /              the single-page web application
POST /api/analyze   body: {"source": "<C source code>"}  ->  JSON analysis result
"""

from flask import Flask, jsonify, render_template, request

import lexer

MAX_SOURCE_CHARS = 200_000          # protects the server from huge inputs

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024   # 2 MB request limit


def json_error(message, status):
    """Uniform JSON error response."""
    return jsonify({"ok": False, "error": message}), status


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze_code():
    # 1. Validate the request body
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return json_error("Request body must be JSON of the form {\"source\": \"...\"}.", 400)

    source = data.get("source")
    if not isinstance(source, str):
        return json_error("The 'source' field must be a string.", 400)
    if not source.strip():
        return json_error("Source code is empty. Please enter some code to analyze.", 400)
    if len(source) > MAX_SOURCE_CHARS:
        return json_error(f"Source code is too long (limit is {MAX_SOURCE_CHARS:,} characters).", 413)

    # 2. Run the lexical analyzer
    try:
        result = lexer.analyze(source)
    except Exception:                # the lexer should never fail; stay safe anyway
        app.logger.exception("Lexer failure")
        return json_error("Internal error while analyzing the code.", 500)

    result["ok"] = True
    return jsonify(result)


# ---- JSON error responses for API clients ----------------------------------
@app.errorhandler(404)
def not_found(_):
    return json_error("Resource not found.", 404)


@app.errorhandler(405)
def method_not_allowed(_):
    return json_error("Method not allowed.", 405)


@app.errorhandler(413)
def too_large(_):
    return json_error("Request is too large.", 413)


if __name__ == "__main__":
    # Debug mode is off so the app behaves the same on every machine.
    app.run(host="127.0.0.1", port=5000, debug=False)
