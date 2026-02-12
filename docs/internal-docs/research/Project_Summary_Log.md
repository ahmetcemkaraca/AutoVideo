# Video Renderer Projesi - Geliştirme Özeti ve Değişiklik Günlüğü

Bu belge, **Otomatik Video Renderer** projesinde yapılan geliştirmeleri, düzeltilen hataları ve eklenen özellikleri özetler.

## 1. Tespit Edilen Hatalar (Bugs)

*   **SIGSEGV Hatası (Kritik):** `audio.py` içerisinde FFmpeg'in `-stream_loop -1` parametresi `concat` demuxer ile kullanıldığında bellek hatalarına (segmentation fault) yol açıyordu.
*   **Donanım Encoder Tespiti:** Eski yöntem sadece string kontrolü yapıyordu, sistemde encoder olsa bile düzgün test edilmediği için bazen seçilemiyordu.
*   **Bozuk Ses Dosyaları:** Müzik klasöründeki bozuk bir ses dosyası tüm render sürecini yarıda kesiyordu (Crash).
*   **Terminal Çıktı Karmaşası:** `Rich` kütüphanesi ile FFmpeg çıktıları aynı anda ekrana basıldığında progress bar'lar bozuluyor ve okunamaz hale geliyordu.
*   **Karakter Kodlama (Encoding):** Windows/Ubuntu arasında Türkçe karakterler (ş, ı, ğ vb.) terminalde bozuk görünüyordu (`??` şeklinde).
*   **Mux Performansı:** Final birleştirme aşamasında işlem tek çekirdek kullanıyordu, bu da süreci yavaşlatıyordu.

## 2. Yapılan Düzeltmeler (Fixes)

*   **FFmpeg Concat Loop Düzeltmesi:** `-stream_loop` yerine, Python tarafında ses dosyaları hedef süreye ulaşana kadar listede çoğaltıldı ve `-t` (duration) parametresi ile kesildi. Bu yöntem SIGSEGV hatasını tamamen çözdü.
*   **Encoder Testi:** `config.py` içerisine gerçek bir FFmpeg encode testi eklendi. Artık sadece isme değil, encoder'ın gerçekten çalışıp çalışmadığına bakılıyor.
*   **Ses Doğrulama (Pre-validation):** Render başlamadan önce tüm ses dosyalarını kontrol eden ve `w64` formatına dönüştüren bir doğrulama adımı eklendi. Bozuk dosyalar otomatik olarak eleniyor.
*   **ASCII Karakter Dönüşümü:** Tüm kaynak kodlardaki Türkçe karakterler İngilizce karşılıklarına (ş->s, ı->i) dönüştürülerek encoding sorunları giderildi.

## 3. Eklenen Özellikler (Features)

*   **Resume (Kaldığı Yerden Devam):** `--resume` bayrağı eklendi. `tmp/last_session.json` dosyası üzerinden son başarılı adımı hatırlayarak (Intro, Loop, Concat vs.) işlemleri atlayabiliyor.
*   **Textual TUI:** Arayüz tamamen `Textual` framework'üne taşındı.
    *   Hata ayıklamayı kolaylaştıran izole log penceresi.
    *   Fare desteği olan etkileşimli menüler.
    *   Video ve Ses seçim ekranları (DataTable).
*   **Batch Render Modu (İstek Üzerine):**
    *   Birden fazla render işini sıraya koyma özelliği.
    *   Bir iş çalışırken diğerlerini hazırlayabilme.
    *   Sıralı otomatik işleme.
*   **Mux Optimizasyonu:** Audio encoding için `-threads 0` (auto) ve AAC-LC profili eklendi. I/O performansını artırmak için `-max_muxing_queue_size 1024` ayarlandı.

## 4. Dosya Yapısı Değişiklikleri

Proje modüler hale getirildi:

```text
video_renderer/
├── app.py           # Textual TUI ana uygulaması
├── batch.py         # Batch kuyruk mantığı (Queue Manager)
├── screens/         # TUI Ekranları
│   ├── home.py
│   ├── batch.py     # Batch arayüzü
│   ├── render.py    # Render ilerleme ekranı
│   └── ...
├── style.tcss       # TUI Stil dosyası
└── main.py          # CLI giriş noktası (--tui desteği ile)
```

## 5. Dağıtım (Deployment)

Sunucuya kod gönderimi için `nc` (netcat) yöntemi standartlaştırıldı.
*   **Önemli:** Medya dosyaları (`.mp4`, `music/`) üzerine yazılmaması için dağıtım komutları sadece kaynak kodları (`.py`, `.tcss`) içerecek şekilde düzenlendi.

---
**Son Durum:** Proje kararlı çalışıyor, UI sorunları giderildi ve seri üretim (batch) yeteneği kazandırıldı.
