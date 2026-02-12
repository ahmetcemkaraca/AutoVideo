# VideoAutomation v1'den v2'ye Migrasyon Kılavuzu

Bu belge, VideoAutomation modülünün v1 sürümünden v2 sürümüne geçiş yaparken dikkate alınması gereken tüm değişiklikleri ve adımları içerir.

## İçindekiler

1. [Neden v2'ye Geçmelisiniz?](#neden-v2ye-geçmelisiniz)
2. [Genel Bakış](#genel-bakış)
3. [API Değişiklikleri Tablosu](#api-değişiklikleri-tablosu)
4. [Modül Bazlı Değişiklikler](#modül-bazlı-değişiklikler)
5. [Adım Adım Migrasyon](#adım-adım-migrasyon)
6. [Örnek Kod Karşılaştırmaları](#örnek-kod-karşılaştırmaları)
7. [Dikkat Edilmesi Gerekenler](#dikkat-edilmesi-gerekenler)
8. [Sorun Giderme](#sorun-giderme)

---

## Neden v2'ye Geçmelisiniz?

### v2'nin Avantajları

| Özellik | v1 | v2 |
|---------|----|----|
| Hata Yönetimi | Temel try/catch | Kapsamlı hata kategorizasyonu ve Circuit Breaker |
| Yapılandırma Doğrulama | Yok | JSON Schema ve runtime validation |
| Durum Yönetimi | Basit JSON | Atomic writes, checksum, otomatik yedekleme |
| Rate Limiting | Manuel | Otomatik günlük kota takibi |
| Monitoring | Yok | Dashboard ve metrik desteği |
| Retry Logic | Basit exponential backoff | Jitter, özelleştirilebilir policy |
| Graceful Shutdown | Yok | Signal handling ve temiz kapatılma |

### Performans İyileştirmeleri

- **Atomic Writes**: Dosya bozulmalarını önler
- **Checksum Doğrulama**: Veri bütünlüğünü garanti eder
- **Otomatik Yedekleme**: Son 5 yedeği tutar
- **Thread-Safe İşlemler**: Çoklu işlem desteği

---

## Genel Bakış

v2, production ortamları için tasarlanmış bir yeniden yazımdır. Ana odak noktaları:

1. **Güvenilirlik**: Hata kurtarma ve veri bütünlüğü
2. **Gözlemlenebilirlik**: Dashboard ve detaylı loglama
3. **Bakım Kolaylığı**: Modüler yapı ve açık API'ler

### Sürüm Bilgisi

```python
# v1
# Sürüm bilgisi yok

# v2
CONFIG_VERSION = 2
CONFIG_FORMAT_VERSION = "2.0"
STATE_VERSION = 2
STATE_FORMAT_VERSION = "2.0"
```

---

## API Değişiklikleri Tablosu

### config.py → config_v2.py

| v1 | v2 | Değişiklik |
|----|----|----------- |
| `PipelineConfig.codec` | `PipelineConfig.render.codec` | Render ayarları alt modüle taşındı |
| `PipelineConfig.target_duration` | `PipelineConfig.render.target_duration` | Render ayarları alt modüle taşındı |
| Yok | `PipelineConfig.render.width/height/fps` | Yeni: Çözünürlük ayarları |
| Yok | `PipelineConfig.render.use_hw_accel` | Yeni: Donanım ivmelesi kontrolü |
| Yok | `PipelineConfig.temp_dir` | Yeni: Geçici dosya dizini |
| Yok | `PipelineConfig.log_level` | Yeni: Log seviyesi |
| Yok | `PipelineConfig.enable_metrics` | Yeni: Metrik toplama |
| `YouTubeConfig` temel | `YouTubeConfig` gelişmiş | Rate limiting, timeout ayarları eklendi |
| `PipelineConfig.from_file()` | `PipelineConfig.from_file()` | Otomatik migrasyon desteği |
| Yok | `PipelineConfig.validate()` | Yeni: Yapılandırma doğrulama |

### state.py → state_v2.py

| v1 | v2 | Değişiklik |
|----|----|----------- |
| `StateManager` (video_renderer'dan) | `StateManager` (yerel) | Bağımsız implementasyon |
| `VideoRecord` temel | `VideoRecord` gelişmiş | file_size, upload_attempts, tags eklendi |
| `stats` dict | `PipelineStats` dataclass | Tip güvenli istatistikler |
| Yok | `PipelineState` dataclass | Versiyonlu state yapısı |
| `PipelineState.add_video()` | `StateManager.add_video()` | Ek parametreler (file_size, tags, metadata) |
| `PipelineState.mark_video_uploaded()` | `StateManager.mark_upload_success()` | Metod yeniden adlandırıldı |
| Yok | `StateManager.mark_upload_attempt()` | Yeni: Upload denemesi kaydı |
| Yok | `StateManager.mark_upload_failed()` | Yeni: Başarısız upload kaydı |
| Yok | `StateManager.validate()` | Yeni: State doğrulama |
| Yok | `StateManager.is_healthy` | Yeni: Sağlık kontrolü |

### youtube.py → youtube_v2.py

| v1 | v2 | Değişiklik |
|----|----|----------- |
| `YouTubeUploader` temel | `YouTubeUploader` gelişmiş | Circuit breaker, retry policy |
| `upload_video()` | `upload_video()` | Otomatik retry dahili |
| `upload_with_exponential_backoff()` | Dahili `_upload_with_retry()` | Fonksiyon sınıf içine alındı |
| Yok | `check_rate_limit()` | Yeni: Kota kontrolü |
| Yok | `get_upload_status()` | Yeni: Upload durumu sorgulama |
| Yok | `delete_video()` | Yeni: Video silme |
| Yok | `stats` property | Yeni: Upload istatistikleri |
| `progress_callback(int, int)` | `progress_callback(MediaUploadProgress)` | Callback tipi değişti |

### pipeline.py → pipeline_v2.py

| v1 | v2 | Değişiklik |
|----|----|----------- |
| `AutomationPipeline` temel | `AutomationPipeline` gelişmiş | Dashboard, monitoring, error tracking |
| `run_once()` | `run_once()` | Çevresel doğrulama eklendi |
| `run_continuous()` | `run_continuous()` | Graceful shutdown, interrupt handling |
| Yok | `_setup_signal_handlers()` | Yeni: Signal yönetimi |
| Yok | `_validate_environment()` | Yeni: Ortam kontrolü |
| Yok | `shutdown()` | Yeni: Temiz kapatılma |
| Yok | `pipeline_resources()` context | Yeni: Kaynak yönetimi |

---

## Modül Bazlı Değişiklikler

### 1. Yapılandırma (config_v2.py)

#### Yeni Enum'lar ve Sabitler

```python
# v2'de yeni
class PrivacyStatus(Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    UNLISTED = "unlisted"

class VideoCodec(Enum):
    H264 = "h264"
    H265 = "h265"
    VP9 = "vp9"
    AV1 = "av1"

YOUTUBE_CATEGORIES = {
    "music": "10",
    "entertainment": "24",
    # ...
}
```

#### RenderConfig Alt Modülü

```python
# v2'de render ayarları ayrı bir dataclass
@dataclass
class RenderConfig:
    codec: str = "av1"
    width: int = 1920
    height: int = 1080
    fps: int = 60
    target_duration: str = "08:00:00"
    video_bitrate: Optional[str] = None
    audio_bitrate: str = "192k"
    use_hw_accel: bool = True
    preferred_encoder: Optional[str] = None

    def validate(self) -> List[str]:
        # Codec, çözünürlük, FPS, süre formatı doğrulaması
        ...
```

#### Doğrulama (Validation)

```python
# v2'de her yapılandırma sınıfının validate() metodu var
config = PipelineConfig.from_file("config.json")
errors = config.validate()
if errors:
    for error in errors:
        print(f"Hata: {error}")
```

### 2. Durum Yönetimi (state_v2.py)

#### VideoRecord Genişletildi

```python
# v1
class VideoRecord:
    video_id: str
    title: str
    created_at: str
    uploaded_at: Optional[str]
    genre: str
    style: str
    duration: str
    local_path: Optional[str]

# v2
@dataclass
class VideoRecord:
    video_id: str
    title: str
    created_at: str
    uploaded_at: Optional[str] = None
    genre: str = ""
    style: str = ""
    duration: str = ""
    local_path: Optional[str] = None
    file_size: Optional[int] = None        # YENİ
    upload_attempts: int = 0               # YENİ
    last_error: Optional[str] = None       # YENİ
    tags: List[str] = field(default_factory=list)  # YENİ
    metadata: Dict[str, Any] = field(default_factory=dict)  # YENİ
```

#### PipelineStats Dataclass

```python
# v2'de istatistikler yapılandırılmış
@dataclass
class PipelineStats:
    total_videos_created: int = 0
    total_uploads_attempted: int = 0
    total_uploads_successful: int = 0
    total_uploads_failed: int = 0
    total_render_time_seconds: float = 0.0
    total_upload_time_seconds: float = 0.0
    last_run: Optional[str] = None
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
```

#### Atomic Writes ve Checksum

```python
# v2'de otomatik checksum ve atomic write
data["checksum"] = self._calculate_checksum(data)

# Önce geçici dosyaya yaz, sonra atomik olarak taşı
temp_file = self.state_file.with_suffix(".tmp")
with open(temp_file, "w") as f:
    json.dump(data, f)
temp_file.replace(self.state_file)  # Atomik işlem
```

### 3. YouTube Uploader (youtube_v2.py)

#### UploadStats ve Rate Limiting

```python
# v2'de upload istatistikleri
@dataclass
class UploadStats:
    uploads_today: int = 0
    last_upload_time: Optional[datetime] = None
    recent_attempts: List[UploadAttempt] = field(default_factory=list)

    def can_upload(self, max_uploads: int, min_interval: timedelta) -> tuple[bool, str]:
        # Günlük kota kontrolü
        # Minimum upload aralığı kontrolü
        ...
```

#### Retry Policy

```python
# v2'de özelleştirilebilir retry
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_attempts=10,
    base_delay=1.0,
    max_delay=600.0,
    exponential_base=2.0,
    jitter=True  # Rastgele gecikme ekler
)
```

#### Circuit Breaker

```python
# v2'de API çağrıları için circuit breaker
self._circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None

# Art arda başarısızlıklar sonrası devreyi açar
# Belirli süre sonra otomatik olarak tekrar dener
```

### 4. Pipeline (pipeline_v2.py)

#### Signal Handling

```python
# v2'de graceful shutdown
def _setup_signal_handlers(self):
    def signal_handler(signum, frame):
        self.logger.info(f"Signal {signum} received, shutting down...")
        self._shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
```

#### Monitoring Dashboard

```python
# v2'de dashboard entegrasyonu
if self.dashboard:
    self.dashboard.set_status(PipelineStatus.RENDERING, "Creating video")
    self.dashboard.add_task(TaskProgress(...))
    self.dashboard.update_task("upload", progress)
```

---

## Adım Adım Migrasyon

### Adım 1: Yedek Alın

```bash
# Mevcut yapılandırma ve state dosyalarını yedekleyin
cp VideoAutomation/config.json VideoAutomation/config.json.v1.bak
cp VideoAutomation/state.json VideoAutomation/state.json.v1.bak
```

### Adım 2: Import'ları Güncelleyin

```python
# v1
from automation.config import PipelineConfig
from automation.state import StateManager
from automation.youtube import YouTubeUploader
from automation.pipeline import AutomationPipeline

# v2
from automation.config_v2 import PipelineConfig, RenderConfig, YouTubeConfig
from automation.state_v2 import StateManager, VideoRecord, PipelineStats
from automation.youtube_v2 import YouTubeUploader, UploadStats
from automation.pipeline_v2 import AutomationPipeline
```

### Adım 3: Yapılandırma Dosyasını Güncelleyin

v1 config.json:
```json
{
  "work_dir": ".",
  "intro_video": "intro.mp4",
  "loop_video": "loop.mp4",
  "target_duration": "08:00:00",
  "codec": "av1",
  "styles": ["relaxing", "calm"],
  "genres": ["ambient", "classical"]
}
```

v2 config.json (otomatik migrasyon ile oluşturulur):
```json
{
  "version": 2,
  "format_version": "2.0",
  "work_dir": ".",
  "intro_video": "intro.mp4",
  "loop_video": "loop.mp4",
  "styles": ["relaxing", "calm"],
  "genres": ["ambient", "classical"],
  "render": {
    "codec": "av1",
    "width": 1920,
    "height": 1080,
    "fps": 60,
    "target_duration": "08:00:00"
  },
  "youtube": {
    "client_secrets_file": "client_secrets.json",
    "max_uploads_per_day": 6,
    "min_upload_interval": 300
  },
  "log_level": "INFO",
  "enable_metrics": false
}
```

**Not**: `PipelineConfig.from_file()` v1 formatını otomatik olarak v2'ye dönüştürür.

### Adım 4: Kodunuzu Güncelleyin

#### Yapılandırma Erişimi

```python
# v1
config = PipelineConfig.from_file("config.json")
duration = config.target_duration
codec = config.codec

# v2
config = PipelineConfig.from_file("config.json")
duration = config.render.target_duration  # render alt modülü
codec = config.render.codec
```

#### State Yönetimi

```python
# v1
state = StateManager(config.state_file)
state.add_video(
    video_id="abc123",
    title="Video Title",
    genre="ambient"
)
state.mark_video_uploaded("abc123")

# v2
state = StateManager(config.state_file, auto_backup=True)
state.add_video(
    video_id="abc123",
    title="Video Title",
    genre="ambient",
    file_size=1024000,  # YENİ: Dosya boyutu
    tags=["ambient", "relaxing"]  # YENİ: Etiketler
)
state.mark_upload_success("abc123")  # Metod adı değişti
```

#### YouTube Upload

```python
# v1
youtube = YouTubeUploader(secrets_file, creds_file)
youtube.authenticate()
video_id = upload_with_exponential_backoff(  # Harici fonksiyon
    youtube, video_path, title, description, tags
)

# v2
youtube = YouTubeUploader(
    secrets_file, creds_file,
    retry_policy=RetryPolicy(max_attempts=5),  # Özelleştirilebilir
    enable_circuit_breaker=True  # YENİ
)
youtube.authenticate()

# Rate limit kontrolü
can_upload, reason = youtube.check_rate_limit(max_uploads=6)
if not can_upload:
    print(f"Upload blocked: {reason}")

# Upload (retry dahili)
video_id = youtube.upload_video(  # Doğrudan metod
    video_path=video_path,
    title=title,
    description=description,
    tags=tags,
    progress_callback=lambda status: print(f"{status.resumable_progress}/{status.total_size}")
)
```

#### Pipeline Çalıştırma

```python
# v1
from automation.pipeline import run_pipeline
run_pipeline(config, continuous=True)

# v2
from automation.pipeline_v2 import AutomationPipeline

pipeline = AutomationPipeline(config, enable_dashboard=True)
try:
    pipeline.run_continuous()
except KeyboardInterrupt:
    pipeline.shutdown()  # Graceful shutdown
```

### Adım 5: Test Edin

```python
# Yapılandırma doğrulama
config = PipelineConfig.from_file("config.json")
errors = config.validate()
if errors:
    print("Yapılandırma hataları:")
    for e in errors:
        print(f"  - {e}")

# State doğrulama
state = StateManager(config.state_file)
is_valid, issues = state.validate()
if not is_valid:
    print("State sorunları:")
    for issue in issues:
        print(f"  - {issue}")

# Sağlık kontrolü
if not state.is_healthy:
    print("Uyarı: Pipeline sağlıklı değil!")
    print(f"Art arda başarısızlık: {state.stats.consecutive_failures}")
```

---

## Örnek Kod Karşılaştırmaları

### Örnek 1: Temel Pipeline Kullanımı

```python
# === v1 ===
from automation.config import PipelineConfig
from automation.pipeline import AutomationPipeline, run_pipeline

config = PipelineConfig.from_file("config.json")
pipeline = AutomationPipeline(config)

# Tek seferlik çalıştırma
pipeline.run_once()

# Sürekli çalıştırma
run_pipeline(config, continuous=True)
```

```python
# === v2 ===
from automation.config_v2 import PipelineConfig
from automation.pipeline_v2 import AutomationPipeline

config = PipelineConfig.from_file("config.json")

# Doğrulama
errors = config.validate()
if errors:
    raise ValueError(f"Config errors: {errors}")

pipeline = AutomationPipeline(config, enable_dashboard=True)

# Tek seferlik
success = pipeline.run_once()

# Sürekli (graceful shutdown ile)
try:
    pipeline.run_continuous()
except KeyboardInterrupt:
    print("Kullanıcı durdurdu")
finally:
    pipeline.shutdown()
```

### Örnek 2: Video Upload ve İstatistikler

```python
# === v1 ===
from automation.youtube import YouTubeUploader, upload_with_exponential_backoff

youtube = YouTubeUploader("client_secrets.json")
youtube.authenticate()

# Manuel retry fonksiyonu
video_id = upload_with_exponential_backoff(
    uploader=youtube,
    video_path=Path("video.mp4"),
    title="My Video",
    description="Description",
    tags=["tag1", "tag2"],
    progress_callback=lambda u, t: print(f"{u}/{t}")
)

# İstatistik yok
```

```python
# === v2 ===
from automation.youtube_v2 import YouTubeUploader
from automation.errors import RetryPolicy

youtube = YouTubeUploader(
    "client_secrets.json",
    retry_policy=RetryPolicy(max_attempts=5, jitter=True),
    enable_circuit_breaker=True
)
youtube.authenticate()

# Rate limit kontrolü
can_upload, reason = youtube.check_rate_limit()
if not can_upload:
    print(f"Cannot upload: {reason}")
    exit(1)

# Upload (retry dahili)
video_id = youtube.upload_video(
    video_path=Path("video.mp4"),
    title="My Video",
    description="Description",
    tags=["tag1", "tag2"],
    progress_callback=lambda s: print(f"{s.resumable_progress}/{s.total_size}")
)

# İstatistikler
stats = youtube.stats
print(f"Today's uploads: {stats.uploads_today}")
print(f"Total bytes: {stats.total_bytes_uploaded}")
```

### Örnek 3: State Yönetimi ve Yedekleme

```python
# === v1 ===
from automation.state import StateManager

state = StateManager(Path("state.json"))

state.add_video(
    video_id="abc123",
    title="My Video",
    genre="ambient"
)

# Manuel yedekleme yok
# Checksum doğrulama yok
```

```python
# === v2 ===
from automation.state_v2 import StateManager

state = StateManager(
    Path("state.json"),
    auto_backup=True,  # Otomatik yedekleme
    backup_count=5     # Son 5 yedeği tut
)

state.add_video(
    video_id="abc123",
    title="My Video",
    genre="ambient",
    file_size=video_path.stat().st_size,  # Dosya boyutu
    tags=["ambient", "relaxing"]           # Etiketler
)

# Doğrulama
is_valid, issues = state.validate()
print(f"State valid: {is_valid}")

# Sağlık kontrolü
if not state.is_healthy:
    print("Warning: Consecutive failures detected!")

# Manuel yedek
backup_path = state.create_backup()
print(f"Backup created: {backup_path}")

# İstatistikler
print(f"Total videos: {state.stats.total_videos_created}")
print(f"Upload success rate: {state.stats.total_uploads_successful}/{state.stats.total_uploads_attempted}")
```

---

## Dikkat Edilmesi Gerekenler

### Kritik Değişiklikler

1. **Render ayarları artık `config.render` altında**
   ```python
   # v1
   duration = config.target_duration

   # v2
   duration = config.render.target_duration
   ```

2. **State metodları yeniden adlandırıldı**
   ```python
   # v1
   state.mark_video_uploaded(video_id)

   # v2
   state.mark_upload_success(video_id)
   ```

3. **Progress callback tipi değişti**
   ```python
   # v1: callback(int, int)
   progress_callback=lambda uploaded, total: print(f"{uploaded}/{total}")

   # v2: callback(MediaUploadProgress)
   progress_callback=lambda status: print(f"{status.resumable_progress}/{status.total_size}")
   ```

4. **Upload fonksiyonu artık metod**
   ```python
   # v1
   video_id = upload_with_exponential_backoff(uploader, ...)

   # v2
   video_id = uploader.upload_video(...)
   ```

### Yeni Bağımlılıklar

v2, aşağıdaki yeni modüllere bağımlıdır:

```python
# automation/errors.py (v2'de yeni)
from .errors import (
    ErrorTracker, RetryPolicy, CircuitBreaker,
    PipelineError, VideoRenderError, ConfigValidationError,
    AuthenticationError, QuotaExceededError,
    categorize_google_api_error
)

# automation/monitoring.py (v2'de yeni)
from .monitoring import (
    MonitorDashboard, PipelineStatus,
    TaskProgress, TaskType
)
```

### Geriye Dönük Uyumluluk

- **Config migrasyonu**: v1 formatındaki config dosyaları otomatik olarak v2'ye dönüştürülür
- **State migrasyonu**: v1 state dosyaları otomatik olarak v2 formatına dönüştürülür
- **API**: Çoğu ana API geriye dönük uyumlu, sadece erişim yolları değişti

### Performans Etkileri

- v2, ek doğrulama ve monitoring nedeniyle hafif bir overhead'e sahip
- Atomic writes ve checksum hesaplama, dosya işlemlerini biraz yavaşlatır
- Dashboard kullanılmadığında (`enable_dashboard=False`), performans v1'e yakın

---

## Sorun Giderme

### Config Dosyası Yüklenemiyor

```python
# v1 config'i v2'ye manuel dönüştürme
config = PipelineConfig.from_file("config.json")

# Hata varsa
errors = config.validate()
for error in errors:
    print(f"Config error: {error}")

# Doğrulama atlamak için (önerilmez)
config = PipelineConfig.from_file("config.json")
# validate() çağırmayın
```

### State Dosyası Bozuk

```python
# v2 otomatik recovery dener
state = StateManager(Path("state.json"))

# Eğer recovery başarısız olursa
if not state.video_count:
    print("State boş, yedekten geri yükleme gerekli olabilir")

    # Manuel yedek kontrolü
    backups = list(Path(".").glob("state_*.json"))
    if backups:
        latest = max(backups, key=lambda p: p.stat().st_mtime)
        print(f"Latest backup: {latest}")
```

### Rate Limit Hatası

```python
# v2'de rate limit kontrolü
can_upload, reason = youtube.check_rate_limit(max_uploads=6)
if not can_upload:
    print(f"Rate limit: {reason}")
    # Bekleme süresini hesapla
    # veya ertele
```

### Graceful Shutdown Çalışmıyor

```python
# Signal handler'ların düzgün kurulduğundan emin olun
import signal

# Windows'ta SIGTERM desteklenmeyebilir
# SIGINT (Ctrl+C) her zaman çalışır

pipeline = AutomationPipeline(config)
try:
    pipeline.run_continuous()
except KeyboardInterrupt:
    print("Shutting down...")
finally:
    pipeline.shutdown()
```

---

## Ek Kaynaklar

- [Testing Guide](./testing-guide.md) - Test yazma kılavuzu
- [Contributing Guide](./contributing-guide.md) - Katkıda bulunma kılavuzu
- [Architecture Docs](../architecture/) - Mimari dokümantasyon

---

## Değişiklik Günlüğü

| Tarih | Sürüm | Değişiklik |
|-------|-------|-----------|
| 2025-02-12 | 1.0 | İlk sürüm |
