#!/usr/bin/env pwsh

[CmdletBinding(PositionalBinding=$false)]
param(
  [switch]$noprompt,
  [string]$venv_name = ".venv"
)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$rootPath = (Resolve-Path -LiteralPath "$scriptPath/..").Path

$argsList = @(
    "--tool-path", (Resolve-Path -LiteralPath "$rootPath/Tools/KotorDiff").Path
    "--venv-name", $venv_name
    "--pip-requirements", (Resolve-Path -LiteralPath "$rootPath/Libraries/PyKotor/requirements.txt").Path
)
if ($noprompt) { $argsList += "--noprompt" }

& "$scriptPath/deps_tool.ps1" @argsList
exit $LASTEXITCODE
