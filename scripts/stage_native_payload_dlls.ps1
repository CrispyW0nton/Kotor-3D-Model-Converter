[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [string]$Platform,

    [Parameter(Mandatory = $true)]
    [string]$Configuration,

    [Parameter(Mandatory = $true)]
    [string]$HostOutDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-Sha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $stream = [IO.File]::Open(
        $Path,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        [IO.FileShare]::Read
    )
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($sha256.ComputeHash($stream)).Replace('-', '')
    }
    finally {
        $sha256.Dispose()
        $stream.Dispose()
    }
}

$stagingRoot = $null

try {
    if ($Platform -notmatch '^[A-Za-z0-9_.-]+$') {
        throw "Invalid platform name '$Platform'."
    }
    if ($Configuration -notmatch '^[A-Za-z0-9_.-]+$') {
        throw "Invalid configuration name '$Configuration'."
    }

    $repoRootPath = [IO.Path]::GetFullPath($RepoRoot)
    $hostOutDirPath = [IO.Path]::GetFullPath($HostOutDir)
    $manifestPath = Join-Path $repoRootPath "native\GhostRigger.PythonPayloadManifest.json"
    $sourceRoot = [IO.Path]::GetFullPath(
        (Join-Path $repoRootPath ("build\vs\{0}\{1}" -f $Platform, $Configuration))
    )

    if (-not (Test-Path -LiteralPath $repoRootPath -PathType Container)) {
        throw "Repository root does not exist: $repoRootPath"
    }
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "Native Python payload manifest does not exist: $manifestPath"
    }

    # Windows PowerShell 5.1 returns a JSON top-level array as one pipeline
    # object, while newer PowerShell versions enumerate it. Normalize both.
    $manifestDocument = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $manifest = @()
    foreach ($manifestEntry in $manifestDocument) {
        $manifest += $manifestEntry
    }
    if ($manifest.Count -eq 0) {
        throw "Native Python payload manifest is empty: $manifestPath"
    }

    $seenProjects = @{}
    $payloads = @()

    # Preflight every exact source before changing either destination. This makes
    # a partial/stale native build fail without destroying the last staged set.
    foreach ($entry in $manifest) {
        if ($null -eq $entry) {
            throw "Native Python payload manifest contains an entry without a project name."
        }

        try {
            $projectName = [string]$entry.project
        }
        catch {
            throw "Native Python payload manifest contains an entry without a project name."
        }

        if ([string]::IsNullOrWhiteSpace($projectName) -or $projectName -notmatch '^[A-Za-z0-9_.-]+$') {
            throw "Native Python payload manifest contains an invalid project name: '$projectName'"
        }

        $projectKey = $projectName.ToUpperInvariant()
        if ($seenProjects.ContainsKey($projectKey)) {
            throw "Native Python payload manifest contains duplicate project '$projectName'."
        }
        $seenProjects[$projectKey] = $true

        $dllName = "$projectName.dll"
        $sourcePath = [IO.Path]::GetFullPath((Join-Path $sourceRoot $dllName))
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            throw "Required native payload DLL is missing: $sourcePath"
        }

        $payloads += [PSCustomObject]@{
            ProjectName = $projectName
            DllName = $dllName
            SourcePath = $sourcePath
            SourceHash = Get-Sha256 -Path $sourcePath
        }
    }

    $stagingRoot = Join-Path (
        [IO.Path]::GetTempPath()
    ) ("GhostStudioNativePayloadStage_{0}" -f [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stagingRoot | Out-Null

    # Host OutDir is normally the exact build source directory. Snapshot first
    # so known stale names can be pruned there without deleting the source set.
    foreach ($payload in $payloads) {
        $stagedPath = Join-Path $stagingRoot $payload.DllName
        Copy-Item -LiteralPath $payload.SourcePath -Destination $stagedPath -Force
        $stagedHash = Get-Sha256 -Path $stagedPath
        if ($stagedHash -ne $payload.SourceHash) {
            throw "SHA-256 mismatch while snapshotting $($payload.ProjectName): expected $($payload.SourceHash), got $stagedHash"
        }
    }

    $destinationRootsByPath = @{}
    foreach ($destinationRoot in @($repoRootPath, $hostOutDirPath)) {
        $destinationKey = $destinationRoot.TrimEnd('\', '/').ToUpperInvariant()
        if (-not $destinationRootsByPath.ContainsKey($destinationKey)) {
            $destinationRootsByPath[$destinationKey] = $destinationRoot
        }
    }
    $destinationRoots = @($destinationRootsByPath.Values)

    foreach ($destinationRoot in $destinationRoots) {
        New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
        foreach ($payload in $payloads) {
            $destinationPath = Join-Path $destinationRoot $payload.DllName
            if (Test-Path -LiteralPath $destinationPath -PathType Leaf) {
                Remove-Item -LiteralPath $destinationPath -Force
            }
        }
    }

    foreach ($payload in $payloads) {
        $stagedPath = Join-Path $stagingRoot $payload.DllName
        foreach ($destinationRoot in $destinationRoots) {
            $destinationPath = Join-Path $destinationRoot $payload.DllName
            Copy-Item -LiteralPath $stagedPath -Destination $destinationPath -Force
        }
    }

    foreach ($payload in $payloads) {
        foreach ($destinationRoot in $destinationRoots) {
            $destinationPath = Join-Path $destinationRoot $payload.DllName
            if (-not (Test-Path -LiteralPath $destinationPath -PathType Leaf)) {
                throw "Native payload DLL was not staged: $destinationPath"
            }
            $destinationHash = Get-Sha256 -Path $destinationPath
            if ($destinationHash -ne $payload.SourceHash) {
                throw "SHA-256 mismatch for $($destinationPath): expected $($payload.SourceHash), got $destinationHash"
            }
        }
    }

    Write-Host (
        "Staged and verified {0} manifest-owned native payload DLLs in '{1}' and '{2}'." -f
        $payloads.Count,
        $repoRootPath,
        $hostOutDirPath
    )
}
catch {
    [Console]::Error.WriteLine("Native payload DLL staging failed: {0}", $_.Exception.Message)
    exit 1
}
finally {
    if ($null -ne $stagingRoot -and (Test-Path -LiteralPath $stagingRoot)) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
