param(
    [string]$VenvPath = ".venv-red",
    [string]$InstanceName = "YOUR_INSTANCE",
    [string]$LogPath = "",
    [switch]$Restart,
    [int[]]$RestartExitCodes = @(26),
    [int]$MaxRestarts = 5,
    [int]$BackoffSeconds = 10
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($InstanceName -eq "" -or $InstanceName -eq "YOUR_INSTANCE") {
    throw "Set -InstanceName to the Red instance created by redbot-setup."
}

$Python = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "python.exe not found in venv: $Python"
}

$RestartCount = 0
do {
    if ($LogPath) {
        & $Python -O -m redbot $InstanceName *>> $LogPath
    } else {
        & $Python -O -m redbot $InstanceName
    }
    $ExitCode = $LASTEXITCODE

    if (-not $Restart -or $ExitCode -eq 0 -or ($RestartExitCodes -notcontains $ExitCode)) {
        exit $ExitCode
    }

    $RestartCount += 1
    if ($MaxRestarts -ge 0 -and $RestartCount -gt $MaxRestarts) {
        Write-Error "Red exited with restart code $ExitCode more than $MaxRestarts time(s); stopping."
        exit $ExitCode
    }

    Write-Host "Red exited with restart code $ExitCode; restarting after $BackoffSeconds seconds..."
    Start-Sleep -Seconds $BackoffSeconds
} while ($Restart)
