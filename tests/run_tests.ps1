Write-Host "Running Bitrate Command Test..."
python tests/test_bitrate_cmd.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Bitrate Test Failed!" -ForegroundColor Red
    exit 1
}
Write-Host "Bitrate Test Passed." -ForegroundColor Green

Write-Host "Running Monitor Mock Test..."
python tests/test_monitor_mock.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Monitor Test Failed!" -ForegroundColor Red
    exit 1
}
Write-Host "Monitor Test Passed." -ForegroundColor Green

Write-Host "All verification tests passed!" -ForegroundColor Green
exit 0
