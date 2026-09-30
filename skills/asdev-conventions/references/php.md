# PHP Patterns

Universal rules first (see SKILL.md), then the four endpoint idioms. Pick the one matching the project you're in — never mix them within a project. For new standalone projects, default to Idiom 1, the RESTful front controller — the newest and strictest of the four.

## File shape

```php
<?php
// /lib/helpers.php  ← path header comment (house habit)
declare(strict_types=1);

namespace Core\Lib; // only the modular-CMS project uses namespaces; the others are flat
```

Typed everything: parameters, returns (`: never` for exit-ing responders, `?string` nullables), `??` with explicit casts for superglobals: `(string) ($_POST['action'] ?? '')`.

## Idiom 1 — RESTful front controller

`api/index.php` parses path + method and dispatches to static controller methods. Central CSRF for all POST/PUT/PATCH/DELETE; one `try/catch (Throwable)` that logs detail and returns a generic 500.

```php
final class Response {
    public static function json(mixed $data, int $status = 200): never {
        http_response_code($status);
        echo json_encode($data, JSON_UNESCAPED_SLASHES);
        exit;
    }
    public static function ok(array $data = []): never { self::json($data + ['ok' => true]); }
    public static function error(string $message, int $status = 400): never { self::json(['error' => $message], $status); }
}
```

Controller method recipe: (1) `Auth::requireUser()`, (2) validate via `Request::str()` + private `validate*()` helpers with `MAX_*` constants, (3) prepared statement **with ownership in the SQL** (`WHERE id = ? AND user_id = ?`), (4) `Response::json()`. After an ownership-scoped UPDATE/DELETE, do an existence check to distinguish 404 from no-op.

## Idiom 2 — Action-dispatch scripts

Each `api/<feature>.php` starts with `require_once 'init.php'` (which handles: env/config, `$pdo`, remember-me re-auth, Origin/Referer CSRF check, stale-`session_version` teardown, maintenance gate, 401 gate), then:

```php
require_once 'init.php';
$input = json_decode(file_get_contents('php://input'), true);
if (!$input || !isset($input['action'])) { echo json_encode(['success' => false, 'message' => 'Invalid payload']); exit; }
$action = $input['action'];
$userId = getCurrentUserId();
// switch/match on $action → free functions from includes/, threaded $pdo first arg: someFn($pdo, $userId, ...)
```

Envelope: `{success: bool, message?: string, ...data}`. Logic lives in `includes/*.php` as free functions; endpoints stay thin.

## Idiom 3 — Admin AJAX actions (mysqli)

```php
<?php
// /core/actions/adm/ajax-pages.php
require_once __DIR__ . '/../../session.php';
header('Content-Type: application/json');
require_once __DIR__ . '/../../init.php';
if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !isset($_POST['csrf_token'])
    || !hash_equals($_SESSION['csrf_token'], $_POST['csrf_token'])) {
    echo json_encode(['status' => 'error', 'message' => t('msg.security_failed')]); exit;
}
$auth = new \Core\Lib\Auth();
if (!$auth->can('manage_pages')) { echo json_encode(['status' => 'error', 'message' => t('msg.permission_denied')]); exit; }
$action = $_POST['action'] ?? '';
```

mysqli OOP with `mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT)`, prepared `bind_param`, shared per-request connection (static `?mysqli $shared` inside `Database`). Envelope: `{status:'success'|'error', message?, html?, data?}`. Log admin actions via `ActivityLogger::logAdminActivity()`.

## Idiom 4 — Layered local gate (localhost-only tool)

For privileged/local tooling endpoints, the full gate stack in order:

```php
<?php
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
$remote = (string) ($_SERVER['REMOTE_ADDR'] ?? '');
if (!in_array($remote, ['127.0.0.1', '::1'], true)) { http_response_code(403); echo json_encode(['ok' => false, 'error' => 'Forbidden — localhost only.']); exit; }
// reject cross-origin POST, then:
require_once __DIR__ . '/lib/helpers.php';
if (!hash_equals(app_csrf_token(), (string) ($_POST['csrf'] ?? ''))) { http_response_code(403); exit; }
app_require_unlock();                       // TTL unlock token
$action = (string) ($_POST['action'] ?? '');
app_audit('sites.' . $action, $_POST);      // audit log before acting
try { echo app_json(dispatch($action)); }
catch (Throwable $e) { echo app_json(['ok' => false, 'error' => $e->getMessage()]); }
```

When JSON gets inlined into HTML (e.g. a snapshot next to a CSRF token), encode with `JSON_HEX_TAG | JSON_INVALID_UTF8_SUBSTITUTE | JSON_PARTIAL_OUTPUT_ON_ERROR` to prevent `</script>` breakout.

## Sessions, auth, secrets

- One idempotent session bootstrap file; cookie params: `HttpOnly`, `SameSite=Lax`, `use_strict_mode`, `Secure` only when actually on HTTPS (branch on local Windows vs prod).
- `session_regenerate_id(true)` on every privilege change (login). Global revocation via a `session_epoch`/`session_version` column checked per request.
- Remember-me: Jaspan split selector:validator token — store SHA-256 of the validator, compare with `hash_equals`, treat selector-match/validator-mismatch as theft (revoke all).
- PDO options: `ERRMODE_EXCEPTION`, `FETCH_ASSOC`, `ATTR_EMULATE_PREPARES => false`, `utf8mb4`.
- `.env` loaded by hand (no dotenv package); config exposed as `define()` constants or getters with defaults. `.htaccess` blocks `.env/.sql/.md` from being served.
- Templates/views are HTML partials: no `<html>/<head>/<body>`, no `<script>/<style>` tags, no `session_start()`, minimal PHP (escaping and loops only). Heavy work belongs in libs/includes.
