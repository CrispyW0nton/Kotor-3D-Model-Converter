#!/usr/bin/env pwsh
# Universal wrapper for compile_tool.py - passes all arguments through

[CmdletBinding(PositionalBinding=$false)]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Passthru
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$pythonScript = Join-Path $scriptDir "compile_tool.py"
$pythonExe = if ($env:pythonExePath) { $env:pythonExePath } else { "python" }

Write-Host "compile_tool.ps1 -> compile_tool.py"
Write-Host "Arguments: $Passthru"
& $pythonExe $pythonScript @Passthru
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

