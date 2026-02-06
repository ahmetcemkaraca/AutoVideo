# Security API Reference

Bu doküman güvenlik modüllerinin detaylı API referansını içerir.

---

## Module: `video_renderer.security`

Input validation ve path security için fonksiyonlar.

### Functions

#### `validate_path(path, allowed_extensions, base_dir, check_exists, max_size)`

Dosya yolunu güvenli bir şekilde validate eder.

**Parameters**:
- `path` (Path | str): Validate edilecek dosya yolu
- `allowed_extensions` (Set[str] | None): İzin verilen dosya uzantıları
- `base_dir` (Path | None): Base directory (path traversal kontrolü için)
- `check_exists` (bool): Dosya varlığını kontrol et (default: False)
- `max_size` (int | None): Maksimum dosya boyutu

**Returns**:
- `Path`: Validate edilmiş Path objesi

**Raises**:
- `PathSecurityError`: Güvenlik ihlali tespit edilirse

**Example**:
```python
from video_renderer.security import validate_path
from pathlib import Path

safe_path = validate_path(
    "video.mp4",
    allowed_extensions={'.mp4', '.mkv'},
    base_dir=Path.cwd(),
    check_exists=True
)
```

#### `validate_video_path(path, base_dir)`

Video dosyası path'ini validate eder.

**Parameters**:
- `path` (Path | str): Video dosyası yolu
- `base_dir` (Path | None): Base directory

**Returns**:
- `Path`: Validate edilmiş video path

**Example**:
```python
from video_renderer.security import validate_video_path

video = validate_video_path("intro.mp4", base_dir=Path.cwd())
```

#### `validate_audio_path(path, base_dir)`

Audio dosyası path'ini validate eder.

**Parameters**:
- `path` (Path | str): Audio dosyası yolu
- `base_dir` (Path | None): Base directory

**Returns**:
- `Path`: Validate edilmiş audio path

**Example**:
```python
from video_renderer.security import validate_audio_path

audio = validate_audio_path("music/track.mp3", base_dir=Path.cwd())
```

#### `sanitize_filename(filename, max_length)`

Dosya ismini güvenli hale getirir.

**Parameters**:
- `filename` (str): Temizlenecek dosya ismi
- `max_length` (int): Maksimum uzunluk (default: 255)

**Returns**:
- `str`: Güvenli dosya ismi

**Example**:
```python
from video_renderer.security import sanitize_filename

safe = sanitize_filename("../../malicious?.mp4")
# Result: "malicious_.mp4"
```

#### `safe_join(base, *paths)`

Güvenli path birleştirme (os.path.join güvenli versiyonu).

**Parameters**:
- `base` (Path): Base directory
- `*paths` (str): Birleştirilecek path parçaları

**Returns**:
- `Path`: Güvenli birleştirilmiş path

**Raises**:
- `PathSecurityError`: Sonuç base directory dışına çıkarsa

**Example**:
```python
from video_renderer.security import safe_join
from pathlib import Path

path = safe_join(Path.cwd(), "user_uploads", "video.mp4")
```

#### `validate_ffmpeg_args(args)`

FFmpeg argümanlarını validate eder.

**Parameters**:
- `args` (List[str]): FFmpeg komut argüman listesi

**Returns**:
- `bool`: True güvenliyse, False değilse

**Example**:
```python
from video_renderer.security import validate_ffmpeg_args

args = ["ffmpeg", "-i", "input.mp4", "output.mp4"]
if validate_ffmpeg_args(args):
    # Güvenli, çalıştır
    pass
```

---

## Module: `video_renderer.secrets`

Secrets ve credential yönetimi için sınıflar ve fonksiyonlar.

### Classes

#### `SecretManager`

Genel secret yönetimi sınıfı.

**Methods**:

##### `__init__(base_dir)`

**Parameters**:
- `base_dir` (Path | None): Base directory (credential dosyaları için)

##### `get_secret_from_env(key, required, default)`

Environment variable'dan secret okur.

**Parameters**:
- `key` (str): Environment variable adı
- `required` (bool): True ise bulunamazsa hata fırlatır (default: True)
- `default` (str | None): required=False için varsayılan değer

**Returns**:
- `str | None`: Secret değeri veya None/default

**Raises**:
- `SecretError`: required=True ve bulunamazsa

**Example**:
```python
from video_renderer.secrets import SecretManager

mgr = SecretManager()
api_key = mgr.get_secret_from_env("API_KEY", required=True)
```

##### `validate_credential_file(filepath, check_age, check_permissions)`

Credential dosyasının güvenliğini validate eder.

**Parameters**:
- `filepath` (Path): Credential dosyası yolu
- `check_age` (bool): Dosya yaşını kontrol et (default: True)
- `check_permissions` (bool): Dosya izinlerini kontrol et (default: True)

**Returns**:
- `bool`: True dosya güvenliyse

**Raises**:
- `InsecureCredentialError`: Dosya güvensizse
- `CredentialExpiredError`: Dosya çok eskiyse

##### `load_credential_file(filepath, validate)`

Credential dosyasını yükler.

**Parameters**:
- `filepath` (Path): Credential dosyası yolu
- `validate` (bool): Güvenlik kontrolü yap (default: True)

**Returns**:
- `Dict[str, Any]`: Credential verileri

**Raises**:
- `InsecureCredentialError`: Dosya güvensizse

#### `YouTubeSecretsManager`

YouTube API secrets için özel yönetici.

**Methods**:

##### `__init__(base_dir)`

**Parameters**:
- `base_dir` (Path | None): Base directory

##### `get_client_secrets_file()`

client_secrets.json dosyasının yolunu döndürür.

**Returns**:
- `Path`: client_secrets.json dosya yolu

##### `get_credentials_file()`

youtube_credentials.json dosyasının yolunu döndürür.

**Returns**:
- `Path`: youtube_credentials.json dosya yolu

##### `load_client_secrets()`

client_secrets.json dosyasını yükler.

**Returns**:
- `Dict[str, Any]`: Client secrets verileri

**Raises**:
- `InsecureCredentialError`: Dosya güvensizse

##### `save_credentials(credentials_data)`

Credentials verilerini güvenli bir şekilde kaydeder.

**Parameters**:
- `credentials_data` (Dict[str, Any]): Kaydedilecek credentials verileri

**Raises**:
- `SecretError`: Kaydetme başarısız olursa

**Example**:
```python
from video_renderer.secrets import YouTubeSecretsManager

yt = YouTubeSecretsManager()

# Yükle
secrets = yt.load_client_secrets()

# Kaydet
yt.save_credentials({"token": "...", "refresh_token": "..."})
```

### Functions

#### `mask_secret(value, visible_chars)`

Secret değerini maskeler (log için).

**Parameters**:
- `value` (str): Maskelenecek değer
- `visible_chars` (int): Görünür karakter sayısı (default: 4)

**Returns**:
- `str`: Maskelenmiş değer (örn: "abcd...xyz")

**Example**:
```python
from video_renderer.secrets import mask_secret

masked = mask_secret("my-secret-api-key-12345", 4)
# Result: "my-s...-12345"
```

---

## Module: `video_renderer.audit`

Audit ve logging için sınıflar ve fonksiyonlar.

### Classes

#### `AuditEventType`

Audit olay tipleri enum'ı.

**Values**:
- `AUTH_SUCCESS` - Başarılı authentication
- `AUTH_FAILURE` - Başarısız authentication
- `AUTH_REFRESH` - Token yenileme
- `FILE_READ` - Dosya okuma
- `FILE_WRITE` - Dosya yazma
- `FILE_DELETE` - Dosya silme
- `FILE_UPLOAD` - Dosya yükleme
- `VIDEO_ENCODE_START` - Video encoding başlangıcı
- `VIDEO_ENCODE_COMPLETE` - Video encoding tamamlandı
- `VIDEO_ENCODE_FAILURE` - Video encoding hatası
- `SECURITY_VIOLATION` - Güvenlik ihlali
- `PATH_TRAVERSAL_ATTEMPT` - Path traversal denemesi
- `COMMAND_INJECTION_ATTEMPT` - Command injection denemesi

#### `AuditLogger`

Audit logger sınıfı.

**Methods**:

##### `__init__(log_dir, app_name, enable_console)`

**Parameters**:
- `log_dir` (Path | None): Log dizini (default: cwd/logs)
- `app_name` (str): Uygulama adı (default: "video_renderer")
- `enable_console` (bool): Konsol loglaması açık mı (default: True)

##### `log_event(event_type, source, details, severity, user_id, ip_address, session_id)`

Audit olayını loglar.

**Parameters**:
- `event_type` (AuditEventType): Olay tipi
- `source` (str): Olay kaynağı (modül/ad)
- `details` (Dict[str, Any]): Olay detayları
- `severity` (str): Severite seviyesi (default: "INFO")
- `user_id` (str | None): Kullanıcı ID
- `ip_address` (str | None): IP adresi
- `session_id` (str | None): Oturum ID

**Example**:
```python
from video_renderer.audit import AuditLogger, AuditEventType

audit = AuditLogger()
audit.log_event(
    event_type=AuditEventType.FILE_READ,
    source="video_encoder",
    details={"filepath": "video.mp4"},
    severity="INFO"
)
```

##### `log_file_access(action, filepath, source, user_id)`

Dosya erişimini loglar.

**Parameters**:
- `action` (str): Action (read/write/delete/upload/download)
- `filepath` (Path): Dosya yolu
- `source` (str): Kaynak modül
- `user_id` (str | None): Kullanıcı ID

**Example**:
```python
audit.log_file_access(
    action="read",
    filepath=Path("video.mp4"),
    source="video_encoder"
)
```

##### `log_auth_event(success, service, source, error)`

Authentication olayını loglar.

**Parameters**:
- `success` (bool): Başarılı mı
- `service` (str): Service adı (youtube, gdrive, vb.)
- `source` (str): Kaynak modül
- `error` (str | None): Hata mesajı (başarısızsa)

**Example**:
```python
audit.log_auth_event(
    success=True,
    service="youtube",
    source="youtube_uploader"
)
```

##### `log_security_violation(violation_type, details, source, severity)`

Güvenlik ihlalini loglar.

**Parameters**:
- `violation_type` (str): İhlal tipi (path_traversal, command_injection)
- `details` (Dict[str, Any]): İhlal detayları
- `source` (str): Kaynak modül
- `severity` (str): Severite (default: "WARNING")

**Example**:
```python
audit.log_security_violation(
    violation_type="path_traversal",
    details={"attempted_path": "../../../etc/passwd"},
    source="video_renderer",
    severity="CRITICAL"
)
```

##### `log_video_encode(video_path, success, duration, error, source)`

Video encoding olayını loglar.

**Parameters**:
- `video_path` (Path): Video dosya yolu
- `success` (bool): Başarılı mı
- `duration` (float | None): İşlem süresi (saniye)
- `error` (str | None): Hata mesajı
- `source` (str): Kaynak modül

**Example**:
```python
audit.log_video_encode(
    video_path=Path("output.mp4"),
    success=True,
    duration=3600.5,
    source="video_encoder"
)
```

##### `get_recent_events(event_type, limit)`

Son olayları okur.

**Parameters**:
- `event_type` (AuditEventType | None): Filtrelenecek olay tipi
- `limit` (int): Maksimum olay sayısı (default: 100)

**Returns**:
- `List[Dict[str, Any]]`: Olay listesi

##### `get_security_events(limit)`

Güvenlik olaylarını okur.

**Parameters**:
- `limit` (int): Maksimum olay sayısı (default: 100)

**Returns**:
- `List[Dict[str, Any]]`: Güvenlik olayları listesi

### Functions

#### `get_audit_logger()`

Global audit logger örneğini döndürür.

**Returns**:
- `AuditLogger`: AuditLogger örneği

**Example**:
```python
from video_renderer.audit import get_audit_logger

audit = get_audit_logger()
audit.log_event(...)
```

#### `init_audit_logger(log_dir, app_name, enable_console)`

Global audit logger'ı başlatır.

**Parameters**:
- `log_dir` (Path | None): Log dizini
- `app_name` (str): Uygulama adı
- `enable_console` (bool): Konsol loglaması

**Returns**:
- `AuditLogger`: AuditLogger örneği

**Example**:
```python
from video_renderer.audit import init_audit_logger
from pathlib import Path

audit = init_audit_logger(
    log_dir=Path("logs"),
    app_name="my_app",
    enable_console=True
)
```

---

## Exception Classes

### `PathSecurityError`

Path güvenliği hatası. Güvenlik ihlali tespit edildiğinde fırlatılır.

### `SecretError`

Secret yönetimi hatası. Genel secret hataları için.

### `CredentialExpiredError`

Credential süresi doldu. Credential çok eski olduğunda fırlatılır.

### `InsecureCredentialError`

Credential güvenliği ihlal edildi. Dosya güvensiz olduğunda fırlatılır.

---

## Constants

### Allowed Extensions

```python
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.flv', '.wmv'}
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.ogg', '.wma', '.aac', '.m4a', '.w64'}
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
```

### File Size Limits

```python
MAX_FILE_SIZE = 100 * 1024 * 1024 * 1024  # 100 GB
MIN_FILE_SIZE = 1024  # 1 KB
```

### Credential Settings

```python
MAX_CREDENTIAL_AGE_DAYS = 90
```

---

## Usage Patterns

### Pattern 1: Secure File Processing

```python
from pathlib import Path
from video_renderer.security import validate_video_path, validate_audio_path
from video_renderer.audit import get_audit_logger

class VideoProcessor:
    def __init__(self):
        self.audit = get_audit_logger()

    def process(self, video_path: Path, audio_path: Path):
        # Validate paths
        safe_video = validate_video_path(video_path, base_dir=Path.cwd())
        safe_audio = validate_audio_path(audio_path, base_dir=Path.cwd())

        # Log access
        self.audit.log_file_access("read", safe_video, "video_processor")

        # Process...
```

### Pattern 2: Secure Configuration

```python
from video_renderer.secrets import YouTubeSecretsManager

class YouTubeUploader:
    def __init__(self):
        self.secrets = YouTubeSecretsManager()

    def authenticate(self):
        # Load secrets
        client_secrets = self.secrets.load_client_secrets()

        # Use environment variable if available
        api_key = self.secrets.get_secret_from_env("YOUTUBE_API_KEY", required=False)

        # Authenticate...
```

### Pattern 3: Security-Aware Error Handling

```python
from video_renderer.security import PathSecurityError
from video_renderer.audit import get_audit_logger, AuditEventType

def safe_process_video(user_input_path: str):
    audit = get_audit_logger()

    try:
        # Validate user input
        safe_path = validate_video_path(user_input_path, base_dir=Path.cwd())

        # Process video
        return process_video(safe_path)

    except PathSecurityError as e:
        # Log security violation
        audit.log_security_violation(
            violation_type="path_traversal",
            details={"attempted_path": user_input_path, "error": str(e)},
            source="video_processor",
            severity="WARNING"
        )

        # Return safe error message
        raise ValueError("Invalid file path") from e
```

---

**Dokümantasyon Sürümü**: 1.0
**Son Güncelleme**: 2025-02-06
