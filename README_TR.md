# AutoVideo - Video İşleme ve Otomasyon Sistemi

[![Python Sürümü](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Lisans](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Gelişmiş video işleme ve otomasyon sistemi. Intro + loop videolarını birleştirerek uzun süren videolar (8-10 saat) oluşturur, otomatik ses işleme, toplu işleme ve bulut entegrasyonu sağlar.

## Özellikler

- **Toplu İşleme**: Farklı yapılandırmalarla birden fazla iş kuyruğa alınabilir
- **Çoklu Seçim**: TUI'de birden fazla video seçilebilir (Boşluk tuşu)
- **Akıllı Toplu**: `*_intro.mp4` ve `*_loop.mp4` çiftlerini otomatik algılar
- **Arka Plan Yükleme**: Videolar işlenirken Google Drive'a otomatik yükler
- **Akıllı Çözünürlük**: Temel Modda kaynak çözünürlüğünü korur
- **Süre Seçenekleri**: Hazır ayarlar, Özel HH:MM:SS veya Rastgele (8-10 saat)
- **Format Desteği**: AV1, H.264, H.265/HEVC kodlama, donanım ivmesi desteği
- **Canlı TUI**: Textual ile oluşturulmuş zengin terminal arayüzü
- **YouTube Entegrasyonu**: Metadata yönetimi ile otomatik YouTube yüklemesi
- **Canlı Yayın Desteği**: YouTube canlı yayını için otomatik çalma listesi oluşturma

## İçindekiler

- [Kurulum](#kurulum)
- [Hızlı Başlangıç](#hızlı-başlangıç)
- [Kullanım](#kullanım)
- [Bileşenler](#bileşenler)
- [Yapılandırma](#yapılandırma)
- [Mimari](#mimari)
- [Sorun Giderme](#sorun-giderme)
- [Katkıda Bulunma](#katkıda-bulunma)

## Kurulum

### Ön Koşullar

- Python 3.10 veya üzeri
- FFmpeg yüklü ve PATH'te olmalı
- (İsteğe bağlı) Google Drive hesabı (bulut yüklemeleri için)
- (İsteğe bağlı) YouTube hesabı (otomatik yüklemeler için)

### Adım 1: Depoyu Klonlayın

```bash
git clone https://github.com/ahmetcemkaraca/AutoVideo
cd AutoVideo
```

### Adım 2: Bağımlılıkları Yükleyin

```bash
# Sanal ortam oluşturun (önerilen)
python -m venv venv

# Sanal ortamı aktifleştirin
# Windows'ta:
venv\Scripts\activate
# Linux/macOS'ta:
source venv/bin/activate

# Bağımlılıkları yükleyin
pip install -r requirements.txt

# Geliştirici modunda yükleyin (isteğe bağlı)
pip install -e .
```

### Adım 3: FFmpeg Kurulumunu Doğrulayın

```bash
ffmpeg -version
ffprobe -version
```

FFmpeg yüklü değilse:

- **Windows**: [ffmpeg.org](https://ffmpeg.org/download.html) adresinden indirin ve PATH'e ekleyin
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg` veya `sudo yum install ffmpeg`

### Adım 4: Google Drive Kurulumu (İsteğe Bağlı)

1. `client_secrets.json` dosyasını proje kök dizinine koyun
2. İlk yüklemeyi yaparken tarayıcı açılacak ve yetki isteyecek
3. Google Drive erane için gerekli izinleri verin

## Hızlı Başlangıç

### İnteraktif TUI Modu (Önerilen)

```bash
python -m video_renderer --tui
```

TUI şunları sağlar:
- **Batch**: Kuyruk yönetimi, iş ekleme, ilerleme izleme
- **Ayarlar**: İşleme ayarları, Drive yükleme aktifleştirme
- **Akıllı Toplu**: Çalışma dizinindeki video çiftlerini otomatik algılama

### CLI Modu

```bash
# İnteraktif sihirbaz
python -m video_renderer

# Akıllı toplu mod (çiftleri otomatik algılar)
python -m video_renderer --batch

# Kesintilen oturumu devam ettir
python -m video_renderer --resume

# Mevcut donanım kodlayıcıları listele
python -m video_renderer --list-hw
```

## Kullanım

### Ana Video İşleyici

#### Tek Video İşleme

```bash
python -m video_renderer
```

İnteraktif sihirbazı takip edin:
1. Intro ve loop videolarını seçin
2. Ses parçalarını seçin
3. Süre ve kodek yapılandırın
4. İşlemeyi başlatın

#### Toplu İşleme

```bash
python -m video_renderer --tui
```

TUI'de:
1. **Toplu** ekranına gidin
2. **Boşluk** tuşu ile birden fazla video seçin
3. Toplu ayarları yapılandırın
4. Birden fazla işi kuyruğa ekleyin
5. İlerlemeyi gerçek zamanlı izleyin

#### Akıllı Toplu Mod

```bash
python -m video_renderer --batch
```

Mevcut dizindeki tüm `*_intro.mp4` / `*_loop.mp4` çiftlerini otomatik olarak algılar ve kuyruğa ekler.

### VideoAutomation Pipeline

VideoAutomation bileşeni YouTube yüklemesi ile uçtan uca otomasyon sağlar.

```bash
cd VideoAutomation

# Yapılandırmayı başlat
python run_automation.py --init

# Müzik dosyalarınızı music/ dizinine ekleyin (MP3, WAV, FLAC)

# YouTube kimlik doğrulama (ilk seferlik)
python run_automation.py --auth-youtube

# Tek video üret
python run_automation.py --config config.json

# Sürekli mod (sonsuz döngü)
python run_automation.py --config config.json --continuous

# İstatistikler
python run_automation.py --stats
```

### VideoLivestream Pipeline

YouTube canlı yayını için otomatik çalma listesi oluşturma.

```bash
cd VideoLivestream

# Yapılandırmayı başlat
python run_livestream.py --init

# Tüm video setleri için çalma listeleri oluştur
python run_livestream.py --generate

# Canlı yayını başlat
python run_livestream.py
```

## Bileşenler

### video_renderer/

TUI arayüzü ile ana video işleme paketi.

- **app.py**: VideoRendererApp - ana TUI uygulaması
- **main.py**: CLI giriş noktası ve sihirbaz
- **ffmpeg.py**: FFmpeg komut çalıştırma ve ilerleme ayrıştırma
- **video.py**: VideoEncoder - kodlama, normalizasyon, birleştirme
- **audio.py**: AudioProcessor - döngüleme, karıştırma, doğrulama
- **config.py**: Kodek yapılandırmaları, donanım kodlayıcı algılama
- **batch.py**: BatchQueue, RenderJob, SmartBatchDetector
- **drive.py**: Google Drive yükleme entegrasyonu
- **screens/**: TUI ekranları (Home, Batch, Settings, Render, Complete, SmartBatch)

### VideoAutomation/

YouTube yüklemesi ile otomatik pipeline.

- **run_automation.py**: CLI giriş noktası
- **automation/pipeline.py**: Uçtan uca otomasyon orchestratörü
- **automation/youtube.py**: YouTube yükleme otomasyonu
- **automation/config.py**: Yapılandırma yönetimi
- **automation/state.py**: Durum kalıcılığı

### VideoLivestream/

YouTube canlı yayın otomasyonu.

- **run_livestream.py**: CLI giriş noktası
- **livestream/scheduler.py**: Yayın planlama
- **livestream/mixer.py**: İçerik karıştırma
- **livestream/streamer.py**: Yayın yönetimi

### video_renderer_ramtest/

İsteğe bağlı çekirdek mantık paylaşımı ile test varyantı.

- **app.py**: Test TUI'si, "Ana İşleyiciyi Kullan" geçişi
- Ana işleyici yapısını test kontrolleriyle yansıtır

## Yapılandırma

### Dosya Yapısı Kuralları

**Ana İşleyici**:
- **Girdi Videoları**: Çalışma dizini (`.mp4`, `.mkv`, `.mov`, vb.)
- **Müzik**: `music/` veya `Music/` dizini
- **Arka Plan Ses**: `background/` dizini veya `bg` öneki olan dosyalar
- **Geçici Dosyalar**: `tmp/` dizini
- **Çıktı**: `final_<ad>_<kodek>_<süre>.mp4` çalışma dizininde
- **Arşiv**: İşleme sonrası kaynak dosya yönetimi için `archive/<zaman damgası>/`

**VideoAutomation**:
- **Yapılandırma**: `config.json` (ayarlar, stiller, türler)
- **YouTube Yetkilendirme**: `client_secrets.json`
- **Müzik**: `music/` (kullanıcı sağlanan MP3/WAV/FLAC dosyaları)
- **Çıktı**: `output/` (işlenmiş videolar)
- **Durum**: `state.json` (video kayıtları ve istatistikler)

**VideoLivestream**:
- **İçerik Setleri**: `content/set{N}_{ad}/` (örn. `set1_ambient/`)
- **Set Başına**: `intro.mp4`, `loop.mp4`, `music/`, `bg/`, `playlists/`
- **Çalma Listeleri**: Set başına 10 JSON dosyası, farklı parça sıralamalarıyla

### Kodek Yapılandırması

Sistem otomatik donanım ivmesi algılama ile çoklu kodek destekler:

**Öncelik Sırası**:
1. NVENC (NVIDIA): `h264_nvenc`, `hevc_nvenc`, `av1_nvenc`
2. QSV (Intel): `h264_qsv`, `hevc_qsv`
3. VAAPI (AMD/Intel Linux): `h264_vaapi`, `hevc_vaapi`
4. Yazılım: `libx264`, `libx265`, `libsvtav1`

### Arka Plan Ses Algılama

`bg` ile başlayan veya `_bg_` içeren dosyalar arka plan sesi olarak kabul edilir. Kazanç değerleri dosya adından ayrıştırılır (örn. `bg_-8.5.mp3` → -8.5 dB).

## Mimari

### Veri Akışı

**İşleme Pipeline'ı**:
```
Video Yolu:  Intro → Normalize → Loop → Normalize → Birleştir (hedef süreye)
Ses Yolu:   Parçalar → Doğrula → Döngüle → Arka planlarla karıştır → Final ses
Final:       Video + Ses → Birleştir → Final çıktı
```

**Paralel Çalıştırma**: Video kodlama ve ses işleme `ThreadPoolExecutor` kullanarak eş zamanlı çalışır.

### TUI Durum Yönetimi

`VideoRendererApp` sınıfı genel uygulama durumunu tutar:
- `queue`: İşleri yönetmek için paylaşılan `BatchQueue` örneği
- `drive_folder_id`, `enable_upload`: Drive entegrasyon ayarları
- `render_mode`: Tek, Intro/Loop veya Toplu modunu takip eder

### Toplu Sistem

İş parçası güvenli `BatchQueue` `RenderJob` nesnelerini yönetir:
- `tmp/batch_queue.json` kalıcılığı
- İlerleme, tamamlama ve hata geri çağırmaları
- UI güncellemeleri ile arka plan iş parçası işleme

### Akıllı Toplu Algılama

`SmartBatchDetector.scan()` intro/loop çiftlerini bulmak için regex kalıpları kullanır:
- Kalıplar: `{ad}_intro.mp4` / `{ad}_loop.mp4`
- Varyasyonlar: `_intro`, `-intro`, `intro` (büyük/küçük harf duyarsız)

## Sorun Giderme

### FFmpeg Bulunamadı

```bash
# FFmpeg'in PATH'te olup olmadığını kontrol edin
ffmpeg -version

# Bulunamadıysa FFmpeg'i kurun:
# Windows: ffmpeg.org adresinden indirin ve PATH'e ekleyin
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg
```

### Donanım İvmesi Çalışmıyor

```bash
# Mevcut donanım kodlayıcıları listeleyin
python -m video_renderer --list-hw

# GPU'nuzun algılanıp algılanmadığını kontrol edin
# NVIDIA: nvidia-smi
# Intel: vainfo (Linux)
```

### Ses Doğrulama Hataları

- Ses dosyalarının MP3, WAV veya FLAC formatında olduğundan emin olun
- Dosyaların bozuk olmadığını kontrol edin
- Dosya yollarının doğru olduğunu doğrulayın

### Google Drive Kimlik Doğrulama Başarısız

- `client_secrets.json` dosyasının proje kök dizininde olduğundan emin olun
- Google Cloud Console ayarlarınızı kontrol edin
- OAuth onay ekranının yapılandırıldığını doğrulayın

### TUI İşleme Sorunları

- Terminalin UTF-8 desteklediğinden emin olun
- Terminal penceresini büyütmeyi deneyin
- Renk Profili uyumluluğunu kontrol edin (mümkünse True Color kullanın)

## Katkıda Bulunma

Katkılarınızı bekliyoruz! İlkeler için [CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bakın.

### Geliştirme Kurulumu

```bash
# Fork'unuzu klonlayın
git clone https://github.com/KULLANICI_ADINIZ/AutoVideo
cd AutoVideo

# Sanal ortam oluşturun
python -m venv venv
source venv/bin/activate  # Windows'ta venv\Scripts\activate

# Geliştirici modunda yükleyin
pip install -e .

# Testleri çalıştırın (varsa)
pytest tests/
```

### Kod Stili

- PEP 8 ilkelerini takip edin
- Uygun yerlerde tür ipuçlarını kullanın
- Fonksiyon ve sınıflara docstring ekleyin
- Fonksiyonları odaklı ve modüler tutun

## Lisans

Bu proje MIT Lisansı altında lisanslanmıştır - detaylar için [LICENSE](LICENSE) dosyasına bakın.

## Teşekkürler

- **Textual**: Mükemmel TUI framework'ü için
- **FFmpeg**: Güçlü multimedya işleme için
- **Rich**: Güzel terminal çıktısı için

## Destek

- **Dokümantasyon**: Detaylı rehberler için [docs/](docs/) adresine bakın
- **Sorunlar**: Hataları [GitHub Issues](https://github.com/ahmetcemkaraca/AutoVideo/issues) üzerinde bildirin
- **Tartışmalar**: [GitHub Discussions](https://github.com/ahmetcemkaraca/AutoVideo/discussions)'a katılın

## Yol Haritası

- [ ] Web tabanlı arayüz
- [ ] Docker konteynerleştirme
- [ ] Daha fazla kodek desteği
- [ ] Eklenti sistemi
- [ ] Dağıtık işleme
- [ ] Bulut işleme desteği

---

**AutoVideo** - Python ve FFmpeg ile video oluşturma otomasyonu.
