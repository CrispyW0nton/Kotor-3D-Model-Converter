#!/usr/bin/env pwsh
# Universal wrapper for deps_tool.py - passes all arguments through

[CmdletBinding(PositionalBinding=$false)]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Passthru
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$pythonScript = Join-Path $scriptDir "deps_tool.py"
$pythonExe = if ($env:pythonExePath) { $env:pythonExePath } else { "python" }

# If pythonExePath is set (venv already created), pass --python-exe and --skip-venv
if ($env:pythonExePath) {
    $Passthru += "--skip-venv"
    $Passthru += @("--python-exe", $env:pythonExePath)
    Write-Host "Using pre-created venv Python: $env:pythonExePath"
}

Write-Host "deps_tool.ps1 -> deps_tool.py"
Write-Host "Arguments: $Passthru"
& $pythonExe $pythonScript @Passthru
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

