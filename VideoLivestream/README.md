# YouTube Livestream System

Tek YouTube kanalında sonsuz canlı yayın. Video setleri 1-3 saat aralıklarla değişir.

## Yapı

```
content/
├── set1_ambient/
│   ├── intro.mp4         # Set başında oynar
│   ├── loop.mp4          # Süre boyunca tekrar eder
│   ├── music/            # Track'ler
│   ├── bg/               # Background sesler
│   └── playlists/        # 10 JSON (farklı sıralamalar)
├── set2_lofi/
│   └── ...
└── set3_nature/
    └── ...
```

## Akış

```
┌────────────────────────────────────────────────┐
│ Set 1: intro → loop (60-180dk) + music + bg   │
├────────────────────────────────────────────────┤
│ Set 2: intro → loop (60-180dk) + music + bg   │
├────────────────────────────────────────────────┤
│ Set 3: intro → loop (60-180dk) + music + bg   │
├────────────────────────────────────────────────┤
│ ... Set 1'e dön, farklı playlist ile devam    │
└────────────────────────────────────────────────┘
```

## Kullanım

```bash
pip install rich

# 1. Setup
python run_livestream.py --init

# 2. Video setlerini content/ içine ekle
#    Her set için: intro.mp4, loop.mp4, music/, bg/

# 3. config.json'a YouTube stream key ekle

# 4. Playlist'leri oluştur
python run_livestream.py --generate

# 5. YAYIN BAŞLAT
python run_livestream.py
```

## Config

```json
{
  "content_dir": "./content",
  "min_duration_minutes": 60,
  "max_duration_minutes": 180,
  "stream": {
    "stream_key": "xxxx-xxxx-xxxx-xxxx"
  }
}
```
