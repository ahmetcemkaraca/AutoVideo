# Video Automation Pipeline

Otomatik, kesintisiz video üretim sistemi:
- 🎵 **Jamendo API** → Royalty-free müzik arama ve indirme
- 🎬 **Video Renderer** → Intro+loop video oluşturma
- 📤 **YouTube API** → Otomatik yükleme

## Kurulum

```bash
# Dependencies
pip install rich requests google-api-python-client google-auth-oauthlib

# Config oluştur
python run_automation.py --init
```

## API Kurulumu

### 1. Jamendo API Key
1. https://developer.jamendo.com adresine git
2. "Apply" ile yeni uygulama oluştur
3. API key'i `config.json` içine koy

### 2. YouTube API
1. https://console.cloud.google.com
2. Yeni proje oluştur
3. YouTube Data API v3 etkinleştir
4. Credentials → OAuth 2.0 Client ID (Desktop App)
5. `client_secrets.json` indir ve bu klasöre koy

## Kullanım

```bash
# Config oluştur
python run_automation.py --init

# YouTube auth (ilk seferlik)
python run_automation.py --auth-youtube

# Tek video üret
python run_automation.py --config config.json

# Sürekli çalıştır
python run_automation.py --config config.json --continuous

# İstatistikler
python run_automation.py --stats
```

## Klasör Yapısı

```
VideoAutomation/
├── config.json              # Ayarlar
├── client_secrets.json      # YouTube OAuth
├── run_automation.py        # CLI entry point
├── intro.mp4               # Video intro
├── loop.mp4                # Video loop
├── automation/             # Ana modüller
│   ├── config.py
│   ├── jamendo.py
│   ├── youtube.py
│   ├── state.py
│   └── pipeline.py
├── video_renderer/         # Render modülü
├── music/                  # İndirilen müzikler
├── output/                 # Oluşturulan videolar
└── state.json              # Kullanılan track'ler
```
