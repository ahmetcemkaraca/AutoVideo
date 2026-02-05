#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Video Renderer - Workspace Cleanup Script (Linux/Mac)
# Removes temporary files and optionally generated videos
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Video Renderer - Temizlik Scripti                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if tmp folder exists
if [ -d "tmp" ]; then
    echo "[*] tmp/ klasoru temizleniyor..."
    rm -f tmp/*.mp4 tmp/*.w64 tmp/*.txt tmp/*.json 2>/dev/null
    echo "[OK] tmp/ klasoru temizlendi."
else
    echo "[!] tmp/ klasoru bulunamadi."
fi

echo ""

# Ask about generated videos
read -p "Cikti videolarini da silmek ister misiniz? (E/H): " CLEAN_VIDEOS
if [[ "$CLEAN_VIDEOS" =~ ^[Ee]$ ]]; then
    echo "[*] Cikti videolari temizleniyor..."
    rm -f final_*.mp4 2>/dev/null
    echo "[OK] Cikti videolari silindi."
else
    echo "[!] Cikti videolari korundu."
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    Temizlik Tamamlandi                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
