Set-Location 'G:\GitHub\Andastra\vendor\PyKotor'
$job = Start-Job -ScriptBlock {
    Set-Location 'G:\GitHub\Andastra\vendor\PyKotor'
    python -m pytest Tools/HolocronToolset/tests/gui/editors/test_erf_editor.py -v
}
$result = $job | Wait-Job -Timeout 120
if ($result) {
    Receive-Job $job
    $exitCode = $job.ChildJobs[0].State
    Remove-Job $job
    exit $LASTEXITCODE
} else {
    Stop-Job $job
    Remove-Job $job
    Write-Host "TIMEOUT: Test execution exceeded 120 seconds"
    exit 1
}
