# VideoLivestream Troubleshooting Guide

Bu belge, VideoLivestream sisteminde karsilasilan yaygin sorunlar ve cozumlerini icermektedir.

---

## Icerik

1. [FFmpeg RTMP Baglanti Sorunlari](#1-ffmpeg-rtmp-baglanti-sorunlari)
2. [YouTube Stream Key Hatalari](#2-youtube-stream-key-hatalari)
3. [Playlist Olusturma Hatalari](#3-playlist-olusturma-hatalari)
4. [Config Dosyasi Hatalari](#4-config-dosyasi-hatalari)
5. [Performans Sorunlari](#5-performans-sorunlari)
6. [Memory Sorunlari](#6-memory-sorunlari)
7. [Ag Baglanti Sorunlari](#7-ag-baglanti-sorunlari)
8. [Video Set Sorunlari](#8-video-set-sorunlari)
9. [Audio Mixing Sorunlari](#9-audio-mixing-sorunlari)
10. [State Yonetimi Sorunlari](#10-state-yonetimi-sorunlari)

---

## 1. FFmpeg RTMP Baglanti Sorunlari

### 1.1 Baglanti Reddedildi Hatasi

**Belirtiler:**
```
[rtmp @ 0x...] Cannot open connection
rtmp://a.rtmp.youtube.com/live2/xxxx: Connection refused
```

**Olası Nedenler:**
- Internet baglantisi kesik
- Firewall RTMP portunu (1935) engelliyor
- YouTube sunucularina erisim yasakli

**Cozum Adimlari:**

1. Internet baglantisini kontrol edin:
```bash
ping a.rtmp.youtube.com
```

2. RTMP portunun acik oldugunu kontrol edin:
```bash
# Linux/Mac
nc -zv a.rtmp.youtube.com 1935

# Windows (PowerShell)
Test-NetConnection -ComputerName a.rtmp.youtube.com -Port 1935
```

3. Firewall kurallarini kontrol edin:
```bash
# Linux (ufw)
sudo ufw allow 1935/tcp

# Windows
netsh advfirewall firewall add rule name="RTMP" dir=out action=allow protocol=tcp localport=1935
```

### 1.2 RTMP Timeout Hatasi

**Belirtiler:**
```
[rtmp @ 0x...] TCP connection timeout
```

**Olası Nedenler:**
- Dusuk baglanti hizi
- Ag tikanikligi
- DNS cozumleme sorunu

**Cozum Adimlari:**

1. DNS ayarlarini kontrol edin:
```bash
# Google DNS kullan
# Linux: /etc/resolv.conf
nameserver 8.8.8.8
nameserver 8.8.4.4

# Windows: Ag ve Paylasim Merkezi > Ag Bagdastirici > DNS
```

2. FFmpeg'de timeout suresini artirin (`streamer.py`):
```python
# build_ffmpeg_stream_args fonksiyonuna ekle
args.extend(["-stimeout", "5000000"])  # 5 saniye timeout
```

### 1.3 FFmpeg Bulunamadi

**Belirtiler:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
```

**Cozum:**

1. FFmpeg'in kurulu oldugunu dogrulayin:
```bash
ffmpeg -version
ffprobe -version
```

2. PATH'e ekleyin:
```bash
# Linux/Mac (.bashrc veya .zshrc)
export PATH=$PATH:/usr/local/bin/ffmpeg

# Windows
# Sistem Ortam Degiskenleri > Path > Duzenle
```

---

## 2. YouTube Stream Key Hatalari

### 2.1 Gecersiz Stream Key

**Belirtiler:**
```
[red]Invalid YouTube stream key (too short)[/]
```
veya
```
YouTube stream key not set in config.json
```

**Olası Nedenler:**
- Stream key girilmemis
- Stream key suresi dolmus
- Yanlis stream key kopyalanmis

**Cozum Adimlari:**

1. YouTube Studio'da stream key'i alin:
   - https://studio.youtube.com
   - Canli Yayin > Yayinla > Stream URL ve anahtar

2. `config.json` dosyasini guncelleyin:
```json
{
  "stream": {
    "stream_key": "xxxx-xxxx-xxxx-xxxx"
  }
}
```

3. Stream key uzunlugunu kontrol edin:
```bash
python -c "key='YOUR_KEY'; print(f'Length: {len(key)} (min 10 required)')"
```

### 2.2 Stream Key Suresi Dolmus

**Belirtiler:**
- YouTube'da "Stream key expired" hatasi
- FFmpeg baglanir ancak yayin gorunmuyor

**Cozum:**

1. YouTube Studio'da yeni stream key olusturun
2. config.json dosyasini guncelleyin
3. Yeniden baslatin:
```bash
python run_livestream.py
```

### 2.3 Farkli RTMP URL Gerekiyor

**Belirtiler:**
- Baglanti basarisiz
- YouTube 4K/60fps yayini

**Cozum:**

Farkli cozunurlukler icin RTMP URL'leri:
```json
{
  "stream": {
    "rtmp_url": "rtmp://a.rtmp.youtube.com/live2",  // 1080p
    // "rtmp_url": "rtmp://a.rtmp.youtube.com/live2",  // 720p
    // "rtmp_url": "rtmp://b.rtmp.youtube.com/live2",  // Yedek
  }
}
```

---

## 3. Playlist Olusturma Hatalari

### 3.1 Playlist Dosyasi Bulunamadi

**Belirtiler:**
```
No playlists in {video_set.name}
```

**Olası Nedenler:**
- Playlist dosyalari olusturulmamis
- `playlists/` klasoru eksik

**Cozum:**

1. Playlist olusturun:
```bash
python run_livestream.py --generate
```

2. Manuel kontrol:
```bash
ls content/sample_set/playlists/
# 01.json, 02.json, ... 10.json olmali
```

### 3.2 Gecersiz Playlist JSON Formatı

**Belirtiler:**
```
JSONDecodeError: Expecting value: line 1 column 1
```

**Olası Nedenler:**
- Bozuk JSON dosyasi
- Encoding sorunu

**Cozum:**

1. JSON dosyasini kontrol edin:
```bash
python -m json.tool content/set1/playlists/01.json
```

2. Gecerli format ornegi:
```json
{
  "name": "Playlist 1",
  "tracks": [
    {"file": "track1.mp3", "order": 1},
    {"file": "track2.mp3", "order": 2}
  ],
  "backgrounds": [
    {"file": "bg_rain.mp3", "gain_db": -8.0}
  ]
}
```

3. Playlist yeniden olusturun:
```bash
rm content/set1/playlists/*.json
python run_livestream.py --generate
```

### 3.3 Muzik Dosyalari Bulunamadi

**Belirtiler:**
```
No music in {video_set.name}
```

**Cozum:**

1. Muzik klasorunu kontrol edin:
```bash
ls content/set1/music/
# .mp3, .wav, .flac, .m4a dosyalari olmali
```

2. Dosya uzantilarini kontrol edin:
```python
# config.py'de desteklenen formatlar
for ext in [".mp3", ".wav", ".flac", ".ogg", ".m4a"]:
    music_files.extend(video_set.music_dir.glob(f"*{ext}"))
```

---

## 4. Config Dosyasi Hatalari

### 4.1 Config Dosyasi Bulunamadi

**Belirtiler:**
```
Config not found: config.json
Run: python run_livestream.py --init
```

**Cozum:**

1. Config olusturun:
```bash
python run_livestream.py --init
```

2. Veya manuel olusturun (`config.json`):
```json
{
  "content_dir": "./content",
  "min_duration_minutes": 60,
  "max_duration_minutes": 180,
  "stream": {
    "rtmp_url": "rtmp://a.rtmp.youtube.com/live2",
    "stream_key": "YOUR_STREAM_KEY",
    "video_bitrate": "4500k",
    "audio_bitrate": "128k",
    "resolution": "1920x1080",
    "fps": 30,
    "preset": "veryfast"
  }
}
```

### 4.2 Gecersiz Config Formatı

**Belirtiler:**
```
Config error: {error_message}
```

**Cozum:**

1. JSON syntax kontrolu:
```bash
python -m json.tool config.json
```

2. Zorunlu alanlari kontrol edin:
   - `content_dir`: Video setlerinin bulundugu klasor
   - `stream.stream_key`: YouTube stream anahtari

### 4.3 Cozunurluk Format Hatasi

**Belirtiler:**
```
ValueError: invalid literal for int() with base 10
```

**Olası Neden:**
- Yanlis resolution formati

**Cozum:**

Gecerli format: `GENISLIKxYUKSEKLIK`
```json
{
  "stream": {
    "resolution": "1920x1080"  // Dogru
    // "resolution": "1080p"   // Yanlis
    // "resolution": "1920*1080" // Yanlis
  }
}
```

---

## 5. Performans Sorunlari

### 5.1 Yuksek CPU Kullanimi

**Belirtiler:**
- %80+ CPU kullanimi
- Gecikmeli yayin
- Dondurmalar

**Olası Nedenler:**
- Cok yuksek preset
- Yetersiz donanim

**Cozum:**

1. Daha hizli preset kullanin:
```json
{
  "stream": {
    "preset": "ultrafast"  // veryfast > faster > fast > medium
  }
}
```

2. Bitrate dusurun:
```json
{
  "stream": {
    "video_bitrate": "3000k",  // 4500k'den dusur
    "resolution": "1280x720"   // 1080p'den dusur
  }
}
```

3. FPS dusurun:
```json
{
  "stream": {
    "fps": 24  // 30'dan dusur
  }
}
```

### 5.2 Dondurarak Yayin (Stuttering)

**Belirtiler:**
- Yayinda takilmalar
- FPS dususleri

**Cozum:**

1. Buffer boyutunu artirin (`mixer.py`):
```python
# build_ffmpeg_stream_args icinde
args.extend(["-bufsize", "9000k"])  # 2x video_bitrate
```

2. Thread sayisini ayarlayin:
```python
args.extend(["-threads", "4"])  # CPU cekirdek sayisina gore
```

### 5.3 Yavas Baslangic

**Belirtiler:**
- Yayin baslamasi uzun suruyor
- Ilk segment gecikmeli

**Cozum:**

1. Video dosyalarini SSD'ye tasiyin
2. Onceden scale edilmis videolar kullanin
3. Intro videosunu kisa tutun

---

## 6. Memory Sorunlari

### 6.1 Yuksek RAM Kullanimi

**Belirtiler:**
- Memory error
- Sistem yavaslamasi
- OOM (Out of Memory) kill

**Olası Nedenler:**
- Buyuk video dosyalari
- Sonsuz loop dosyalari
- Concat listesinde cok fazla dosya

**Cozum:**

1. Loop sayisini azaltin (`mixer.py`):
```python
def create_music_concat(self, tracks: List[Path], loop_count: int = 20):  # 50'den 20'ye
```

2. FFmpeg memory limiti:
```python
args.extend(["-mem_limit", "512M"])  # Linux'ta calisir
```

### 6.2 Memory Leak

**Belirtiler:**
- Zamanla artan RAM kullanimi
- Gunlerce calisan yayinda crash

**Cozum:**

1. Periyodik restart (dis script):
```bash
# crontab
0 */6 * * * pkill -f run_livestream.py && cd /path/to/VideoLivestream && python run_livestream.py
```

2. Segment bazli temizlik (`scheduler.py`):
```python
# Her segment sonrasi
import gc
gc.collect()
```

---

## 7. Ag Baglanti Sorunlari

### 7.1 Yayin Kesintileri

**Belirtiler:**
- Periyodik kesintiler
- "Stream interrupted" mesajlari

**Cozum:**

1. Ag arabelleklerini artirin:
```python
# streamer.py'de retry mantigi zaten var
self.max_retries = 10  # 5'ten 10'a
self.retry_delay = 10.0  # 5'ten 10'a
```

2. YouTube'a yakin VPN kullanin

### 7.2 Bandwidth Yetersizligi

**Belirtiler:**
- Duguk kalite
- Piksellesme
- Buffering

**Cozum:**

1. Bandwidth testi yapin:
```bash
speedtest-cli
# Upload hizi video_bitrate'den en az %20 fazla olmali
# 4500k bitrate icin minimum 5.5 Mbps upload gerekir
```

2. Bitrate'i upload hizina gore ayarlayin:
```json
{
  "stream": {
    "video_bitrate": "2500k"  // 3 Mbps upload icin
  }
}
```

### 7.3 Ag Donusumunde Yayin Dusmesi

**Belirtiler:**
- WiFi/Ethernet degisiminde yayin duruyor
- IP degisiminde baglanti kopuyor

**Cozum:**

1. Sabit IP kullanin
2. Ag arayuzunu kilitleyin:
```bash
# Linux
nmcli con mod <connection> connection.autoconnect yes
```

---

## 8. Video Set Sorunlari

### 8.1 Video Set Bulunamadi

**Belirtiler:**
```
No video sets in content/ directory
```

**Cozum:**

1. Dogru klasor yapisini olusturun:
```
content/
├── set1/
│   ├── intro.mp4
│   ├── loop.mp4
│   ├── music/
│   │   ├── track1.mp3
│   │   └── track2.mp3
│   ├── bg/
│   │   └── ambient.mp3
│   └── playlists/
│       ├── 01.json
│       └── 02.json
```

2. Video dosyalarini kontrol edin:
```bash
ls content/set1/*.mp4
# intro.mp4 ve loop.mp4 olmali
```

### 8.2 Intro/Loop Video Eksik

**Belirtiler:**
```
No intro video in {set_path}
No loop video in {set_path}
```

**Cozum:**

1. Desteklenen formatlarda dosya ekleyin:
   - `.mp4`, `.mkv`, `.webm`, `.mov`

2. Dosya isimlerini kontrol edin:
```bash
# Dogru
content/set1/intro.mp4
content/set1/loop.mp4

# Yanlis
content/set1/Intro.mp4  # Buyuk harf
content/set1/intro_video.mp4  # Farkli isim
```

### 8.3 Video Codec Uyumsuzlugu

**Belirtiler:**
```
[libx264 @ ...] codec not supported
```

**Cozum:**

1. Video codec kontrolu:
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 content/set1/intro.mp4
```

2. FFmpeg otomatik donusturur, ancak sorun cikarsa:
```bash
ffmpeg -i input.avi -c:v libx264 -c:a aac output.mp4
```

---

## 9. Audio Mixing Sorunlari

### 9.1 Ses Cikmıyor

**Belirtiler:**
- Yayinda video var ama ses yok

**Olası Nedenler:**
- Music klasoru bos
- Audio codec uyumsuzlugu

**Cozum:**

1. Music dosyalarini kontrol edin:
```bash
ls -la content/set1/music/
```

2. Audio codec kontrolu:
```bash
ffprobe -i content/set1/music/track1.mp3 -show_streams -select_streams a
```

3. Gecici olarak ses testi:
```bash
ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 10 -c:a aac test_audio.aac
```

### 9.2 Ses Seviyesi Cok Dusuk/Yuksek

**Belirtiler:**
- Arka plan sesi cok duyuluyor
- Muzik cok kisik

**Cozum:**

1. Background gain ayari (`config.json` veya playlist):
```json
{
  "backgrounds": [
    {"file": "bg.mp3", "gain_db": -12.0}  // -8'den -12'ye (daha kisik)
  ]
}
```

2. Genel audio level:
```python
# mixer.py'de
audio_filter = "[2:a]volume=1.5[main];..."  # 1.5x volume
```

### 9.3 Audio Sync Sorunu

**Belirtiler:**
- Video ile audio senkron degil

**Cozum:**

1. Video FPS ile audio sample rate uyumu:
```python
args.extend(["-ar", "48000"])  # 48kHz standard
args.extend(["-async", "1"])   # Audio sync
```

2. A/V sync filter:
```python
args.extend(["-af", "aresample=async=1"])
```

---

## 10. State Yonetimi Sorunlari

### 10.1 State Dosyasi Bozuk

**Belirtiler:**
```
Warning: Could not load state: {error}
```

**Cozum:**

1. State dosyasini silin ve yeniden olusturun:
```bash
rm state.json
python run_livestream.py
```

2. Manuel duzeltme:
```json
{
  "current_channel_index": 0,
  "channels": {},
  "total_segments": 0,
  "started_at": null,
  "last_rotation": null
}
```

### 10.2 Playlist Index Kayması

**Belirtiler:**
- Ayni playlist surekli caliyor
- Sira atlanıyor

**Cozum:**

1. State'i sifirlayin:
```bash
python -c "
import json
with open('state.json', 'w') as f:
    json.dump({'current_channel_index': 0, 'channels': {}, 'total_segments': 0}, f)
"
```

2. Modulo hesaplamasini kontrol edin (`state.py`):
```python
state.current_playlist_index = (state.current_playlist_index + 1) % playlist_count
```

---

## Ek: Hata Ayiklama Araclari

### Loglama Etkinlestirme

```python
# scheduler.py basina ekleyin
import logging
logging.basicConfig(level=logging.DEBUG)
```

### FFmpeg Komutunu Goruntuleme

```python
# scheduler.py'de prepare_segment sonrasi
args = self.prepare_segment(...)
print(" ".join(args))  # Komutu yazdir
```

### Dry-Run Kullanimi

```bash
python run_livestream.py --dry-run
```

### Video Set Listeleme

```bash
python run_livestream.py --list
```

### Istatistik Goruntuleme

```bash
python run_livestream.py --stats
```

---

## Sik Kullanilan Komutlar

```bash
# Ilk kurulum
python run_livestream.py --init

# Playlist olustur
python run_livestream.py --generate

# Video setleri listele
python run_livestream.py --list

# Test modu
python run_livestream.py --dry-run

# Istatistikler
python run_livestream.py --stats

# Yayini baslat
python run_livestream.py

# Ozel config ile
python run_livestream.py --config /path/to/config.json
```

---

## Iletisim ve Destek

Sorun devam ederse:
1. `state.json` icerigini kontrol edin
2. FFmpeg ciktisini inceleyin
3. Sistem loglarini kontrol edin (`journalctl -u livestream` veya Windows Event Viewer)
