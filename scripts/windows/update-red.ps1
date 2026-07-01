[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$VenvPath = ".venv-red",
    [string]$BackupSource = "",
    [string]$BackupDestination = "",
    [switch]$SkipBackup,
    [switch]$UpgradeCogs,
    [switch]$Yes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE: $FilePath $($Arguments -join ' ')"
    }
}

$Python = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found in venv: $Python"
}
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Redctl = Join-Path $RepoRoot "scripts\redctl.py"

if ($SkipBackup) {
    if (-not $Yes) {
        throw "Skipping backup requires both -SkipBackup and -Yes."
    }
    Write-Warning "Backup was explicitly skipped."
} else {
    if (-not $BackupSource -or -not $BackupDestination) {
        throw "Provide -BackupSource and -BackupDestination, or explicitly pass -SkipBackup -Yes."
    }
    if ($PSCmdlet.ShouldProcess($BackupSource, "Create verified Red data backup")) {
        $BackupArgs = @($Redctl, "backup", "--source", $BackupSource, "--destination", $BackupDestination)
        if ($Yes) { $BackupArgs += "--yes" }
        Invoke-Checked $Python @BackupArgs
    }
}

if ($PSCmdlet.ShouldProcess($VenvPath, "Upgrade Red-DiscordBot")) {
    Invoke-Checked $Python -m pip install --upgrade Red-DiscordBot
    Invoke-Checked $Python $Redctl check
}

Write-Host "Discord commands to run manually after review:"
Write-Host "  [p]cog update"
if ($UpgradeCogs) {
    Write-Host "  [p]reload <cog>"
}
