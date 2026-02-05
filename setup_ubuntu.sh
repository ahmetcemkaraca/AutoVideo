#!/bin/bash

# Renkler
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🎬 Video Renderer Kurulum Sihirbazı${NC}"
echo "----------------------------------------"

# 1. Root kontrolü
if [ "$EUID" -ne 0 ]; then 
  echo -e "${RED}✗ Lütfen bu scripti root olarak çalıştırın (sudo bash setup_ubuntu.sh)${NC}"
  exit 1
fi

# 2. System Update & Dependencies
echo -e "${BLUE}📦 Sistem paketleri güncelleniyor ve yükleniyor...${NC}"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-full \
    ffmpeg \
    git \
    nano \
    unzip

# 3. NVIDIA GPU Kurulumu (varsa)
echo -e "${BLUE}🎮 NVIDIA GPU kontrolü yapılıyor...${NC}"
if lspci | grep -i nvidia > /dev/null 2>&1; then
    echo -e "${GREEN}✓ NVIDIA GPU bulundu. Driver yükleniyor...${NC}"
    
    # Ubuntu driver auto-install
    DEBIAN_FRONTEND=noninteractive apt-get install -y ubuntu-drivers-common
    
    # Try 'install' command (newer), fallback to 'autoinstall'
    ubuntu-drivers install || ubuntu-drivers autoinstall || echo -e "${YELLOW}⚠ Otomatik driver kurulumu basarisiz. Manuel kurulum gerekebilir.${NC}"
    
    # NVIDIA CUDA toolkit
    echo -e "${BLUE}📦 CUDA Toolkit yükleniyor...${NC}"
    DEBIAN_FRONTEND=noninteractive apt-get install -y nvidia-cuda-toolkit || echo -e "${YELLOW}⚠ CUDA Toolkit yüklenemedi.${NC}"
    
    echo -e "${YELLOW}⚠ GPU driver kurulum adimlari tamamlandi. Eger hata aldiysaniz 'nvidia-smi' komutunu kontrol edin.${NC}"
    echo -e "${YELLOW}  Sunucuyu yeniden başlatmanız gerekebilir: reboot${NC}"
else
    echo -e "${YELLOW}⚠ NVIDIA GPU bulunamadı. CPU encoding kullanılacak.${NC}"
fi

# 4. Klasör yapısı
echo -e "${BLUE}📂 Klasörler oluşturuluyor...${NC}"
APP_DIR=$(pwd)
echo "Calisma dizini: $APP_DIR"

mkdir -p "$APP_DIR/music"
mkdir -p "$APP_DIR/archive"
mkdir -p "$APP_DIR/tmp"

# 5. Python Virtual Environment
echo -e "${BLUE}🐍 Python virtual environment oluşturuluyor...${NC}"
cd "$APP_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# 6. Python Dependencies
echo -e "${BLUE}📦 Python paketleri yükleniyor...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 7. Package install (development mode)
if [ -f "pyproject.toml" ]; then
    echo -e "${BLUE}📦 Video-renderer paketi yükleniyor...${NC}"
    pip install -e .
fi

# 8. Permission fix
chmod +x run.py 2>/dev/null || true
chmod +x setup_ubuntu.sh 2>/dev/null || true

# 9. Create run script
cat > "$APP_DIR/run.sh" << 'EOF'
#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

python3 run.py
EOF
chmod +x "$APP_DIR/run.sh"

echo "----------------------------------------"
echo -e "${GREEN}✅ Kurulum Tamamlandı!${NC}"
echo ""
echo -e "${BLUE}Kullanım:${NC}"
echo "1. Videolarınızı '$APP_DIR' klasörüne atın."
echo "2. Programı başlatın:"
echo -e "${GREEN}    ./run.sh${NC}"
echo ""
if lspci | grep -i nvidia > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ GPU kullanmak için sunucuyu yeniden başlatın: reboot${NC}"
fi
echo "----------------------------------------"
