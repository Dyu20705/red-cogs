param(
    [string]$VenvPath = ".venv-red",
    [switch]$SkipBackup,
    [switch]$UpgradeCogs,
    [switch]$Yes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $SkipBackup -and -not $Yes) {
    throw "Create a backup first or pass -SkipBackup with an explicit operational reason."
}

$Python = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found in venv: $Python"
}

& $Python -m pip install --upgrade Red-DiscordBot
python scripts/redctl.py check

Write-Host "Discord commands to run manually after review:"
Write-Host "  [p]cog update"
if ($UpgradeCogs) {
    Write-Host "  [p]reload <cog>"
}
