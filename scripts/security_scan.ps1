# Security Scanner Script for Windows
# Bu script projenin güvenlik taramasını yapar

Write-Host "=== AutoVideo Security Scanner ===" -ForegroundColor Cyan
Write-Host ""

# Install security tools if not installed
Write-Host "[1/4] Güvenlik araçları kontrol ediliyor..." -ForegroundColor Yellow

try {
    $null = Get-Command bandit -ErrorAction Stop
} catch {
    Write-Host "Bandit installing..." -ForegroundColor Yellow
    pip install bandit
}

try {
    $null = Get-Command safety -ErrorAction Stop
} catch {
    Write-Host "Safety installing..." -ForegroundColor Yellow
    pip install safety
}

# Run bandit
Write-Host ""
Write-Host "[2/4] Bandit security taraması çalıştırılıyor..." -ForegroundColor Cyan
bandit -r . -f json -o bandit_report.json
bandit -r . -f txt -o bandit_report.txt

# Run safety
Write-Host ""
Write-Host "[3/4] Safety dependency taraması çalıştırılıyor..." -ForegroundColor Cyan
safety check --json > safety_report.json
safety check > safety_report.txt

# Run pip-audit
Write-Host ""
Write-Host "[4/4] Pip-audit dependency taraması çalıştırılıyor..." -ForegroundColor Cyan
try {
    pip-audit --format json --output pip_audit_report.json
    pip-audit --output pip_audit_report.txt
} catch {
    Write-Host "pip-audit not available, skipping..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Tarama tamamlandı! Raportlar:" -ForegroundColor Green
Write-Host "  - bandit_report.json/txt"
Write-Host "  - safety_report.json/txt"
Write-Host "  - pip_audit_report.json/txt"
