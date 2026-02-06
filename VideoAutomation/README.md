# Video Automation Pipeline

Otomatik, kesintisiz video üretim sistemi:
- 🎬 **Video Renderer** → Intro+loop video oluşturma
- 🎵 **Local Music** → Kendi müzik dosyalarınızı kullanın
- 📤 **YouTube API** → Otomatik yükleme

## Kurulum

```bash
# Dependencies
pip install rich requests google-api-python-client google-auth-oauthlib

# Config oluştur
python run_automation.py --init

# Müzik dosyalarınızı music/ klasörüne ekleyin (MP3, WAV, FLAC)
```

## YouTube API Kurulumu

1. https://console.cloud.google.com adresine gidin
2. Yeni proje oluşturun
3. YouTube Data API v3'ü etkinleştirin
4. Credentials → OAuth 2.0 Client ID (Desktop App)
5. `client_secrets.json` dosyasını indirin ve bu klasöre koyun

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
│   ├── config.py           # Configuration management
│   ├── youtube.py          # YouTube upload automation
│   ├── pipeline.py         # End-to-end automation orchestrator
│   └── state.py            # State persistence
├── video_renderer/         # Render modülü
├── music/                  # Müzik dosyalarınız (MP3/WAV/FLAC)
├── output/                 # Oluşturulan videolar
└── state.json              # Durum bilgisi
```

## Konfigürasyon

`config.json` dosyası ile şu ayarları yapabilirsiniz:
- `styles`: Video stil etiketleri (örn: "relaxing", "calm", "meditative")
- `genres`: Müzik türleri (örn: "ambient", "classical", "jazz")
- `target_duration`: Hedef video süresi (örn: "08:00:00" = 8 saat)
- `codec`: Video kodek (av1, h264, h265)
- `youtube`: YouTube API ayarları ve metadata şablonları
