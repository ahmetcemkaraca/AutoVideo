#!/bin/bash

# Video Renderer Startup Script (Linux/macOS)
# Robust dependency checking and environment setup with proper terminal handling

# ANSI Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Terminal cleanup handler
cleanup_terminal() {
    # Restore terminal settings
    if command -v stty &> /dev/null; then
        stty sane 2>/dev/null
    fi
    # Flush output streams
    sync
}

# Register cleanup on exit
trap cleanup_terminal EXIT
trap 'echo -e "\n${YELLOW}İptal edildi.${NC}"; exit 130' INT TERM

# 0. Check for Updates
echo -e "${BLUE}Checking for updates...${NC}"
if command -v git &> /dev/null; then
    # Capture output, merge stderr to stdout
    GIT_OUT=$(git pull 2>&1)
    
    # Check if we are already up to date
    # Note: "Already up to date." is the standard message, but language might vary.
    # We check if it *doesn't* contain "Already up to date" (and assume success if it didn't fail).
    if [[ "$GIT_OUT" == *"Already up to date."* ]]; then
        echo -e "${GREEN}System is up to date.${NC}"
    elif [[ "$GIT_OUT" == *"fatal"* || "$GIT_OUT" == *"error"* ]]; then
        echo -e "${RED}Git update failed:${NC}"
        echo "$GIT_OUT"
        echo -e "${YELLOW}Continuing with current version...${NC}"
    else
        echo -e "${YELLOW}Updates detected and downloaded.${NC}"
        echo -e "${BLUE}$GIT_OUT${NC}"
        echo -e "${GREEN}Restarting script to apply updates...${NC}"
        exec "$0" "$@"
        exit 0
    fi
else
    echo -e "${YELLOW}Git not found, skipping update check.${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Video Renderer Başlatıcı${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"

# 1. Check Python 3
echo -n "Checking Python 3... "
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}OK ($(python3 --version))${NC}"
else
    echo -e "${RED}MISSING${NC}"
    echo -e "${YELLOW}Python 3 yukleniyor...${NC}"
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
    else
        echo -e "${RED}HATA: apt-get bulunamadi. Lutfen Python 3.8+ manuel yukleyin.${NC}"
        read -p "Cikis icin Enter'a basin..."
        exit 1
    fi
fi

# 2. Check FFmpeg
echo -n "Checking FFmpeg... "
if command -v ffmpeg &> /dev/null; then
    # Parse version just to be sure
    FFVER=$(ffmpeg -version | head -n1 | grep -oP 'version \K.[^ ]+')
    echo -e "${GREEN}OK (v$FFVER)${NC}"
else
    echo -e "${RED}MISSING${NC}"
    echo -e "${YELLOW}FFmpeg yukleniyor...${NC}"
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y ffmpeg
    else
        echo -e "${RED}HATA: apt-get bulunamadi. Lutfen FFmpeg manuel yukleyin.${NC}"
        read -p "Cikis icin Enter'a basin..."
        exit 1
    fi
fi

# 3. Check/Create Venv
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Virtual Environment (venv) olusturuluyor...${NC}"
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}HATA: venv olusturulamadi. 'python3-venv' paketinin yuklu oldugundan emin olun.${NC}"
        exit 1
    fi
    echo -e "${GREEN}Venv olusturuldu.${NC}"
    
    # First time setup: Upgrade pip and install requirements
    echo -e "${BLUE}Bagimliliklar yukleniyor...${NC}"
    ./$VENV_DIR/bin/pip install --upgrade pip
    ./$VENV_DIR/bin/pip install -r requirements.txt
else
    # Check if we need to update requirements (simple check)
    # Ideally we'd compare timestamps or use pip-sync, but for now just check modules
    if ! ./$VENV_DIR/bin/python3 -c "import textual" &> /dev/null; then
        echo -e "${YELLOW}Eksik paketler tespit edildi. Yukleniyor...${NC}"
        ./$VENV_DIR/bin/pip install -r requirements.txt
    fi
fi

# 4. Run Application
echo -e "${GREEN}▶ Uygulama başlatılıyor...${NC}\n"

source "$VENV_DIR/bin/activate"

# Check if run.py exists
if [ ! -f "run.py" ]; then
    echo -e "${RED}✗ HATA: run.py bulunamadi!${NC}"
    read -p "Çıkış için Enter'a basın..."
    exit 1
fi

# Run Python application with proper subprocess handling
if [ $# -gt 0 ]; then
    # Passthrough mode with arguments
    python3 run.py "$@"
    EXIT_CODE=$?
else
    # Interactive mode
    python3 run.py
    EXIT_CODE=$?
fi

# Exit with the application's exit code
exit $EXIT_CODE
