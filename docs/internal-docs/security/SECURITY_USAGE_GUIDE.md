# Security Usage Guide

Bu doküman güvenlik modüllerinin pratik kullanım örneklerini içerir.

---

## Hızlı Başlangıç

### 1. Security Modülünü Kullanma

```python
from pathlib import Path
from video_renderer.security import (
    validate_video_path,
    validate_audio_path,
    safe_join,
    sanitize_filename
)

# Kullanıcı girdisi validate etme
user_input = "../uploads/video.mp4"  # Tehlikeli olabilir!

try:
    safe_video = validate_video_path(user_input, base_dir=Path.cwd())
    print(f"Safe path: {safe_video}")
except Exception as e:
    print(f"Security error: {e}")
```

### 2. Audit Logger Kullanma

```python
from video_renderer.audit import init_audit_logger, AuditEventType

# Logger başlat
audit = init_audit_logger(
    log_dir=Path("logs"),
    app_name="my_app",
    enable_console=True
)

# Dosya erişimi logla
audit.log_file_access(
    action="read",
    filepath=Path("video.mp4"),
    source="video_encoder"
)

# Güvenlik ihlali logla
audit.log_security_violation(
    violation_type="path_traversal",
    details={"attempted": "../../../etc/passwd"},
    source="video_processor",
    severity="CRITICAL"
)
```

### 3. Secrets Yönetimi

```python
from video_renderer.secrets import YouTubeSecretsManager

# Manager başlat
yt = YouTubeSecretsManager()

# Environment variable'dan secret
api_key = yt.get_secret_from_env("YOUTUBE_API_KEY", required=False)

# Credentials yükle
credentials = yt.load_credentials()

# Credentials kaydet (atomik)
yt.save_credentials({"token": "new_token"})
```

---

## Gerçek Hayat Senaryoları

### Senaryo 1: Video Upload İşlemi

```python
from pathlib import Path
from video_renderer.security import validate_video_path
from video_renderer.audit import get_audit_logger

class VideoUploadHandler:
    def __init__(self):
        self.audit = get_audit_logger()

    def handle_upload(self, user_uploaded_file: str, target_dir: Path):
        # 1. Dosya yolunu validate et
        try:
            safe_path = validate_video_path(
                user_uploaded_file,
                base_dir=target_dir,
                check_exists=True
            )
        except Exception as e:
            # Güvenlik hatasını logla
            self.audit.log_security_violation(
                violation_type="invalid_file",
                details={"file": user_uploaded_file, "error": str(e)},
                source="upload_handler"
            )
            raise ValueError("Invalid file path") from e

        # 2. Dosya erişimini logla
        self.audit.log_file_access(
            action="upload",
            filepath=safe_path,
            source="upload_handler"
        )

        # 3. İşleme devam et
        return self.process_video(safe_path)
```

### Senaryo 2: Batch Processing

```python
from pathlib import Path
from video_renderer.security import validate_video_path, safe_join
from video_renderer.audit import AuditEventType, get_audit_logger

class BatchProcessor:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.audit = get_audit_logger()

    def process_batch(self, file_list: list[str]) -> list[Path]:
        safe_paths = []

        for filename in file_list:
            # Dosya ismini sanitize et
            safe_name = sanitize_filename(filename)

            # Güvenli path oluştur
            safe_path = safe_join(self.base_dir, "videos", safe_name)

            # Validate et
            try:
                validated = validate_video_path(safe_path, base_dir=self.base_dir)
                safe_paths.append(validated)

                # Log
                self.audit.log_file_access("read", validated, "batch_processor")

            except Exception as e:
                self.audit.log_event(
                    event_type=AuditEventType.SECURITY_WARNING,
                    source="batch_processor",
                    details={"file": filename, "error": str(e)},
                    severity="WARNING"
                )

        return safe_paths
```

### Senaryo 3: YouTube Upload

```python
from pathlib import Path
from video_renderer.secrets import YouTubeSecretsManager
from video_renderer.audit import get_audit_logger, AuditEventType

class YouTubeUploader:
    def __init__(self):
        self.secrets = YouTubeSecretsManager()
        self.audit = get_audit_logger()

    def authenticate(self) -> bool:
        try:
            # Client secrets yükle
            client_secrets = self.secrets.load_client_secrets()

            # Environment variable'dan API key kontrol et
            api_key = self.secrets.get_secret_from_env(
                "YOUTUBE_API_KEY",
                required=False
            )

            # Authentication logic...
            success = self._do_authenticate(client_secrets, api_key)

            # Log
            self.audit.log_auth_event(
                success=success,
                service="youtube",
                source="youtube_uploader"
            )

            return success

        except Exception as e:
            # Hata logla (secret'ları maskele)
            self.audit.log_event(
                event_type=AuditEventType.AUTH_FAILURE,
                source="youtube_uploader",
                details={"error": str(e)},
                severity="ERROR"
            )
            return False
```

---

## Entegrasyon Checklist

Mevcut kodunuza güvenlik eklerken bu checklist'i kullanın:

### ✅ Step 1: Import Security Modules

```python
from video_renderer.security import validate_video_path, validate_audio_path
from video_renderer.audit import get_audit_logger
from video_renderer.secrets import YouTubeSecretsManager
```

### ✅ Step 2: Validate User Input

```python
# Kullanıcı girdisi her zaman validate edilmeli
safe_path = validate_video_path(user_input, base_dir=base_dir)
```

### ✅ Step 3: Log Security Events

```python
audit = get_audit_logger()
audit.log_file_access("read", safe_path, "module_name")
```

### ✅ Step 4: Use Safe Path Operations

```python
# unsafe: path / user_input
# safe: safe_join(path, user_input)

from video_renderer.security import safe_join
safe_path = safe_join(base_dir, user_input)
```

### ✅ Step 5: Handle Security Errors

```python
from video_renderer.security import PathSecurityError

try:
    safe_path = validate_video_path(user_input)
except PathSecurityError as e:
    # Log and return generic error
    audit.log_security_violation(...)
    raise ValueError("Invalid file") from e
```

---

## Testing Security

### Unit Test Örneği

```python
import pytest
from pathlib import Path
from video_renderer.security import validate_video_path, PathSecurityError

def test_path_traversal_prevention():
    """Path traversal saldırısının engellendiğini test et"""
    base_dir = Path("/safe/base")

    with pytest.raises(PathSecurityError):
        validate_video_path("../../../etc/passwd", base_dir=base_dir)

def test_valid_path():
    """Geçerli path'in kabul edildiğini test et"""
    base_dir = Path("/safe/base")
    test_file = base_dir / "video.mp4"

    # Test dosyasını oluştur
    test_file.touch()

    result = validate_video_path("video.mp4", base_dir=base_dir)
    assert result == test_file
```

### Integration Test Örneği

```python
def test_secure_file_upload(tmp_path, caplog):
    """Güvenli dosya upload işlemini test et"""
    from video_renderer.security import validate_video_path
    from video_renderer.audit import get_audit_logger

    audit = get_audit_logger()
    test_file = tmp_path / "test.mp4"
    test_file.touch()

    # Başarılı upload
    result = validate_video_path(test_file, base_dir=tmp_path)
    assert result == test_file

    # Audit log kontrolü
    # ... log kontrolü
```

---

## CI/CD Entegrasyonu

GitHub Actions örneği:

```yaml
name: Security Scan

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install security tools
        run: |
          pip install bandit safety pip-audit

      - name: Run Bandit
        run: bandit -r . -f txt -o bandit_report.txt

      - name: Run Safety
        run: safety check --json > safety_report.json

      - name: Run pip-audit
        run: pip-audit --format json --output pip_audit_report.json

      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            bandit_report.txt
            safety_report.json
            pip_audit_report.json
```

---

## Troubleshooting

### Sorun: "Path base directory dışında" hatası

**Çözüm**: `base_dir` parametresini doğru şekilde belirtin:

```python
# Yanlış
validate_video_path("../video.mp4")

# Doğru
validate_video_path("../video.mp4", base_dir=Path.cwd())
```

### Sorun: Audit log dosyası oluşturulamıyor

**Çözüm**: Log dizinini oluşturun veya yolu kontrol edin:

```python
from pathlib import Path

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

audit = init_audit_logger(log_dir=log_dir)
```

### Sorun: Credential dosyası bulunamıyor

**Çözüm**: Environment variable kullanın veya doğru yolu belirtin:

```python
import os
from video_renderer.secrets import YouTubeSecretsManager

# Environment variable ile
os.environ["YOUTUBE_CLIENT_SECRETS"] = "/path/to/client_secrets.json"

yt = YouTubeSecretsManager()
```

---

**Sürüm**: 1.0
**Son Güncelleme**: 2025-02-06
