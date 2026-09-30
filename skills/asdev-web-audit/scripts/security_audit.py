"""Static security scanner for web projects (PHP / JS / TS / Python).

This is a regex scanner: it catches recognisable mistakes, not clever ones. A
clean run is not a proof of safety - it only means nothing obvious matched.

Detection notes
---------------
SQL injection is matched in two stages rather than one clever pattern: first
confirm a string literal actually contains a query (SELECT..FROM, UPDATE..SET,
INSERT INTO, DELETE FROM), then look for interpolation or concatenation of a
variable. The single-regex version this replaces only caught a variable that was
*followed* by a concat dot, so it missed `"WHERE id = $id"`, `"{$_GET['id']}"`
and `"WHERE id = " . $_GET['id']` - the three commonest shapes.

Run from a project root. See _common.py for shared behaviour and .auditignore.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    Report, ReadError, cli, git_tracked, in_scope, is_comment_line, iter_files,
    read_text, scope_active,
)

# realpath on both sides: this suite is reached through a junction into the setup repo, and an
# abspath comparison of the two spellings never matched, so the scanner flagged its own patterns.
SELF_DIR = os.path.dirname(os.path.realpath(__file__))

# --- SQL -------------------------------------------------------------------
# Require a clause pair so prose like "UPDATE failed for $id" isn't a query.
SQL_CONTEXT = re.compile(
    r"\bSELECT\b[^\n]{0,200}?\bFROM\b"
    r"|\bINSERT\s+INTO\b"
    r"|\bUPDATE\b[^\n]{0,120}?\bSET\b"
    r"|\bDELETE\s+FROM\b"
    r"|\bREPLACE\s+INTO\b",
    re.IGNORECASE,
)

# String literals, so SQL and the variable must share one literal.
STRING_LITERALS = re.compile(
    r'"((?:[^"\\\n]|\\.)*)"'
    r"|'((?:[^'\\\n]|\\.)*)'"
    r"|`((?:[^`\\]|\\.)*)`"
)

# A variable interpolated inside a literal: PHP "$x"/"{$x}", JS ${x}, py {x}.
INTERPOLATED = re.compile(r"\$\w|\$\{|\{\w")

# Names of interpolated variables, so we can prove what each one holds.
INTERP_VARS = re.compile(r"\$\{?(\w+)")

# A variable PROVEN to hold a "?,?,?" placeholder list, built the standard way:
#   $ph = implode(',', array_fill(0, count($ids), '?'));
#   $in = str_repeat('?,', count($x) - 1) . '?';
# Interpolating one of these into `IN (...)` is a correct prepared statement -
# the string is only question marks, never data. Proving it by the same-file
# assignment (not by name) keeps `IN ($userIds)` with raw data still flagged.
PLACEHOLDER_ASSIGN = re.compile(
    r"\$(\w+)\s*=\s*[^;\n]*?"
    # array_fill(...'?') - allow the nested count($x) paren before the '?'
    r"(?:array_fill\s*\([^;\n]*?['\"]\?['\"]|str_repeat\s*\(\s*['\"]\?)"
)

# Concatenation anchored to a quote, so `$a . $b` elsewhere on the line is not
# mistaken for query building.
SQL_CONCAT = re.compile(
    r"[\"'`]\s*\.\s*\$"          # PHP  "..." . $var
    r"|\$[\w\[\]'\"\->]*\s*\.\s*[\"'`]"  # PHP  $var . "..."
    r"|[\"'`]\s*\+\s*\w"          # JS   "..." + var
    r"|\w\s*\+\s*[\"'`]"          # JS   var + "..."
    r"|[\"'`]\s*%\s*[\(\w]"       # PY   "..." % (x,)
    r"|[\"'`]\s*\.\s*format\s*\(" # PY   "...".format(x)
)

# --- output ----------------------------------------------------------------
SUPERGLOBAL_OUT = re.compile(
    r"(?:\becho\b|\bprint\b|<\?=)[^;\n]{0,100}?\$_(?:GET|POST|REQUEST|COOKIE)\b"
)
DOM_SINK = re.compile(
    r"\.(?:innerHTML|outerHTML)\s*=\s*[^;\n]*(?:\$\{|\+\s*\w)"
    r"|\.insertAdjacentHTML\s*\([^;\n]*(?:\$\{|\+\s*\w)"
)
DOCUMENT_WRITE = re.compile(r"document\.write\s*\(")
# Expressions interpolated into a template literal.
TEMPLATE_EXPR = re.compile(r"\$\{([^{}]*)\}")
# A call taking nothing or a string literal - ${header()}, ${icon('cog')} -
# renders a trusted component. It isn't the user data this rule looks for.
# A call over a variable is still flagged: the regex cannot see what's inside.
COMPONENT_CALL = re.compile(
    r"^[A-Za-z_$][\w$.]*\(\s*(?:'[^']*'|\"[^\"]*\")?\s*\)$"
)
# If any of these appear on the line, the value is being neutralised.
ESCAPED = re.compile(
    r"htmlspecialchars|htmlentities|\bescapeHtml\b|\besc\s*\(|strip_tags"
    r"|filter_var|\bintval\b|\(int\)|textContent|encodeURIComponent|\bsanitiz",
    re.IGNORECASE,
)

# --- misc ------------------------------------------------------------------
DANGEROUS_FUNC = re.compile(
    r"(?<![\w>$.\-])(?:eval|exec|system|shell_exec|passthru|popen|proc_open"
    r"|pcntl_exec|assert|create_function)\s*\("
    r"|new\s+Function\s*\("
)
UNSAFE_DESERIALIZE = re.compile(
    r"\bunserialize\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)"
)
SECRET_ASSIGN = re.compile(
    r"(?i)\b(?:password|passwd|pwd|api[_-]?key|secret|access[_-]?key"
    r"|private[_-]?key|auth[_-]?token|bearer)\w*\s*(?:=>|=|:)\s*"
    r"['\"]([^'\"\n]{8,})['\"]"
)
SECRET_DEFINE = re.compile(
    r"(?i)define\s*\(\s*['\"](?:DB_PASS\w*|API_KEY|\w*SECRET\w*|\w*TOKEN)['\"]"
    r"\s*,\s*['\"]([^'\"\n]{8,})['\"]"
)
SECRET_LITERAL = re.compile(
    r"AKIA[0-9A-Z]{16}"                 # AWS access key id
    r"|sk_live_[0-9a-zA-Z]{16,}"        # Stripe live secret
    r"|ghp_[0-9A-Za-z]{36}"             # GitHub PAT
    r"|xox[baprs]-[0-9A-Za-z-]{10,}"    # Slack token
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
PLACEHOLDER = re.compile(
    r"(?i)^(?:your|example|placeholder|change[_ -]?me|xxx|test|dummy|todo|sample"
    r"|password|secret|null|true|false|\.{3}|<.*>|\{\{.*\}\}|\$\{.*\}|%\w+%)"
)
WEAK_RANDOM = re.compile(
    r"(?i)\b(?:token|secret|salt|nonce|csrf|session_id|password|api_?key)\w*\s*"
    r"=[^;\n]{0,60}?(?:\bmt_rand\s*\(|\brand\s*\(|\buniqid\s*\(|Math\.random\s*\()"
)
WEAK_HASH = re.compile(
    r"\b(?:md5|sha1)\s*\(\s*\$?(?:password|passwd|pwd)"
    r"|\b(?:password|passwd|pwd)\w*\s*=\s*(?:md5|sha1)\s*\(",
    re.IGNORECASE,
)
INSECURE_TLS = re.compile(
    r"CURLOPT_SSL_VERIFY(?:PEER|HOST)\s*(?:,|=>)\s*(?:false|0)\b"
    r"|rejectUnauthorized\s*:\s*false"
    r"|verify\s*=\s*False",
    re.IGNORECASE,
)
CORS_WILDCARD = re.compile(
    r"Access-Control-Allow-Origin['\"]?\s*[:,]\s*['\"]?\*", re.IGNORECASE
)
DISPLAY_ERRORS = re.compile(
    r"display_errors\s*['\"]?\s*,\s*['\"]?(?:1|on|true)\b"
    r"|ini_set\s*\(\s*['\"]display_errors['\"]\s*,\s*['\"]?(?:1|on|true)",
    re.IGNORECASE,
)

EXAMPLE_FILE = re.compile(r"\.(?:example|sample|dist|template)$|\.env\.example")


def _sql_findings(report: Report, rel: str, num: int, line: str, ext: str,
                  ph_vars: frozenset = frozenset()) -> None:
    literals = [g for match in STRING_LITERALS.finditer(line)
                for g in match.groups() if g]
    sql_literals = [lit for lit in literals if SQL_CONTEXT.search(lit)]
    if not sql_literals:
        return

    for lit in sql_literals:
        if not INTERPOLATED.search(lit):
            continue
        names = set(INTERP_VARS.findall(lit))
        # Safe iff every interpolated variable is a proven placeholder list -
        # then the interpolated text is only "?,?,?", never data.
        if names and names <= ph_vars:
            continue
        report.add(rel, num, "SQL_INJECTION",
                   "variable interpolated into a query string; "
                   "use a prepared statement")
        return

    if SQL_CONCAT.search(line):
        names = set(INTERP_VARS.findall(line))
        if names and names <= ph_vars:
            return
        report.add(rel, num, "SQL_INJECTION",
                   "query built by concatenation; use a prepared statement")


def _scan_line(report: Report, rel: str, num: int, line: str, ext: str,
               ph_vars: frozenset = frozenset()) -> None:
    _sql_findings(report, rel, num, line, ext, ph_vars)

    if ext == ".php" and SUPERGLOBAL_OUT.search(line) and not ESCAPED.search(line):
        report.add(rel, num, "XSS_OUTPUT",
                   "superglobal echoed without htmlspecialchars()")

    if ext in (".js", ".ts"):
        if DOCUMENT_WRITE.search(line):
            report.add(rel, num, "XSS_DOM",
                       "document.write() is an XSS sink; build nodes instead")
        elif DOM_SINK.search(line) and not ESCAPED.search(line):
            # Only complain when actual data is interpolated. `${header()}`
            # renders a trusted component and is how these projects compose
            # markup; `${row.title}` is the shape that gets you owned.
            exprs = [e.strip() for e in TEMPLATE_EXPR.findall(line)]
            data_exprs = [e for e in exprs if e and not COMPONENT_CALL.match(e)]
            if data_exprs or not exprs:
                sample = data_exprs[0][:40] if data_exprs else "concatenated value"
                report.add(rel, num, "XSS_DOM",
                           f"unescaped '{sample}' written as HTML; "
                           "wrap it in escapeHtml() or set textContent")

    if DANGEROUS_FUNC.search(line):
        report.add(rel, num, "DANGEROUS_FUNC",
                   "executes a command or evaluates code at runtime")

    if UNSAFE_DESERIALIZE.search(line):
        report.add(rel, num, "UNSAFE_DESERIALIZE",
                   "unserialize() on user input allows object injection")

    if WEAK_RANDOM.search(line):
        report.add(rel, num, "WEAK_RANDOM",
                   "security value from a non-cryptographic RNG; "
                   "use random_bytes()/crypto.getRandomValues()")

    if WEAK_HASH.search(line):
        report.add(rel, num, "WEAK_HASH",
                   "md5/sha1 on a password; use password_hash()")

    if INSECURE_TLS.search(line):
        report.add(rel, num, "INSECURE_TLS", "TLS certificate verification disabled")

    if CORS_WILDCARD.search(line):
        report.add(rel, num, "CORS_WILDCARD",
                   "Access-Control-Allow-Origin: * exposes this endpoint to any origin")

    if DISPLAY_ERRORS.search(line):
        report.add(rel, num, "DISPLAY_ERRORS",
                   "display_errors enabled; errors must be logged, not shown")


def _secret_findings(report: Report, rel: str, num: int, line: str) -> None:
    if EXAMPLE_FILE.search(rel):
        return
    if SECRET_LITERAL.search(line):
        report.add(rel, num, "HARDCODED_SECRET",
                   "recognisable credential literal in source")
        return
    for regex in (SECRET_ASSIGN, SECRET_DEFINE):
        match = regex.search(line)
        if not match:
            continue
        value = match.group(1)
        if PLACEHOLDER.match(value.strip()) or "$" in value or len(set(value)) <= 2:
            continue
        report.add(rel, num, "HARDCODED_SECRET",
                   "literal credential; move it to a git-ignored .env")
        return


def _repo_hygiene(report: Report, root: str) -> None:
    """Checks about the repository itself rather than any one line of code."""
    env_path = os.path.join(root, ".env")
    if not os.path.exists(env_path):
        return

    # A tracked .env means the secrets are in git history for good.
    if git_tracked(root, ".env") is True:
        report.add(".env", None, "ENV_TRACKED_IN_GIT",
                   "committed to git - rotate the secrets and untrack it "
                   "(git rm --cached .env), history rewrite if sensitive")

    if not any(os.path.exists(os.path.join(root, name)) for name in
               (".env.example", ".env.sample", ".env.dist", ".env.template")):
        report.add(".env", None, "ENV_NO_EXAMPLE",
                   "no committed .env.example sibling documenting the keys")

    # Under Apache (XAMPP/Plesk), a webroot .env is served as plain text
    # unless blocked. Only meaningful when the scan root is a webroot.
    htaccess = os.path.join(root, ".htaccess")
    if not os.path.exists(htaccess):
        report.add(".env", None, "ENV_NOT_BLOCKED",
                   "no .htaccess at this level; if this directory is an "
                   "Apache webroot, /.env is downloadable")
    else:
        try:
            if ".env" not in read_text(htaccess):
                report.add(".htaccess", None, "ENV_NOT_BLOCKED",
                           ".htaccess does not mention .env - add a deny "
                           "rule (FilesMatch \"^\\.env\")")
        except ReadError as exc:
            report.unread(".htaccess", str(exc))


def run(args) -> Report:
    report = Report("security_audit")
    root = args.path
    # Hygiene describes repo state, not the current diff - in scoped runs
    # (--changed / --staged) it only fires when the relevant files are in
    # scope, so a pre-commit hook can't be blocked by pre-existing state.
    if not scope_active() or in_scope(".env") or in_scope(".htaccess"):
        _repo_hygiene(report, root)
    for rel in iter_files([".php", ".js", ".ts", ".py"], root):
        path = os.path.join(root, rel)
        # Never scan these scanners: they contain the patterns as literals.
        if os.path.realpath(path).startswith(SELF_DIR + os.sep):
            continue
        try:
            raw = read_text(path)
        except ReadError as exc:
            report.unread(rel, str(exc))
            continue
        report.scanned += 1
        ext = os.path.splitext(rel)[1]
        # Variables proven to hold a placeholder list anywhere in this file.
        ph_vars = frozenset(PLACEHOLDER_ASSIGN.findall(raw))
        for num, line in enumerate(raw.splitlines(), 1):
            stripped = line.strip()
            if not stripped or is_comment_line(stripped, ext):
                continue
            _scan_line(report, rel, num, line, ext, ph_vars)
            _secret_findings(report, rel, num, line)
    return report


if __name__ == "__main__":
    cli(run, "Scan a web project for common security mistakes.")
