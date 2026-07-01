[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$VenvPath = ".venv-red",
    [string]$InstanceName = "YOUR_INSTANCE",
    [switch]$SkipJavaCheck,
    [switch]$Upgrade
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-Command($Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found on PATH: $Name"
    }
}

Require-Command python
Require-Command git
if (-not $SkipJavaCheck) {
    Require-Command java
}

if ($PSCmdlet.ShouldProcess($VenvPath, "Create or update Red virtual environment")) {
    if (-not (Test-Path -LiteralPath $VenvPath)) {
        python -m venv $VenvPath
    }
    $Python = Join-Path $VenvPath "Scripts\python.exe"
    & $Python -m pip install --upgrade pip wheel
    if ($Upgrade) {
        & $Python -m pip install --upgrade Red-DiscordBot
    } else {
        & $Python -m pip install Red-DiscordBot
    }
}

Write-Host "Next steps:"
Write-Host "  $VenvPath\Scripts\redbot-setup"
Write-Host "  .\scripts\windows\start-red.ps1 -VenvPath $VenvPath -InstanceName $InstanceName"
