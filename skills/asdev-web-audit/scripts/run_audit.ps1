param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AuditArgs
)

$ErrorActionPreference = 'Stop'
$auditScript = Join-Path $PSScriptRoot 'audit_all.py'
$candidates = @()
if ($env:AUDIT_PYTHON) {
    $candidates += $env:AUDIT_PYTHON
}
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $candidates += $pythonCommand.Source
}
$python = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $python) {
    Write-Error 'Python 3 was not found. Set AUDIT_PYTHON to its executable path.'
    exit 2
}

& $python -X utf8 $auditScript @AuditArgs
exit $LASTEXITCODE
