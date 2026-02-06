#!/bin/bash
# Security Scanner Script
# Bu script projenin güvenlik taramasını yapar

set -e

echo "=== AutoVideo Security Scanner ==="
echo ""

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Install security tools if not installed
echo "[1/4] Güvenlik araçları kontrol ediliyor..."

if ! command -v bandit &> /dev/null; then
    echo -e "${YELLOW}Bandit installing...${NC}"
    pip install bandit
fi

if ! command -v safety &> /dev/null; then
    echo -e "${YELLOW}Safety installing...${NC}"
    pip install safety
fi

# Run bandit
echo ""
echo "[2/4] Bandit security taraması çalıştırılıyor..."
bandit -r . -f json -o bandit_report.json || true
bandit -r . -f txt -o bandit_report.txt || true

# Run safety
echo ""
echo "[3/4] Safety dependency taraması çalıştırılıyor..."
safety check --json > safety_report.json || true
safety check > safety_report.txt || true

# Run pip-audit
echo ""
echo "[4/4] Pip-audit dependency taraması çalıştırılıyor..."
pip-audit --format json --output pip_audit_report.json || true
pip-audit --output pip_audit_report.txt || true

echo ""
echo -e "${GREEN}Tarama tamamlandı! Raportlar:${NC}"
echo "  - bandit_report.json/txt"
echo "  - safety_report.json/txt"
echo "  - pip_audit_report.json/txt"
