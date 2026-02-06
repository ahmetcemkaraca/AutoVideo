# Proje Geliştirme Özeti ve Durum Raporu

Bu belge, yürütülen çalışmaların, tespit edilen hataların, istenen özelliklerin ve geliştirme notlarının bir özetini içermektedir.

## 1. Tespit Edilen Hatalar (Bugs)

*   **Pip Kurulum Hatası**: Ubuntu sunucuda `pip install` yapılırken alınan `externally-managed-environment` hatası.
    *   *Durum*: Sanal ortam (venv) kullanımı veya `--break-system-packages` bayrağı ile aşılabilir.
*   **Import Hatası (`ModuleNotFoundError`)**: `render.py` dosyası çalıştırıldığında `video_renderer` modülünün bulunamaması.
    *   *Durum*: `render.py` içerisine dinamik `sys.path` eklemesi yapılarak **Düzeltildi**.

## 2. İstenen Özellikler (Feature Requests)

### Video Renderer (Görüntü İşleyici)
*   **Akıllı Toplu İşlem (Smart Batch)**:
    *   Klasördeki `*_intro.mp4` ve `*_loop.mp4` dosyalarının otomatik tespit edilip eşleştirilmesi.
    *   Her çift için özelleştirilebilir müzik ve arka plan sesi ayarları.
*   **Google Drive Entegrasyonu**:
    *   Render tamamlandığında videonun otomatik olarak Google Drive'a yüklenmesi.
    *   Yükleme işleminin bir sonraki render ile eş zamanlı (asenkron) yapılması.
    *   Kullanıcı yetkilendirmesi (Auth) ve oturumun kalıcı olması.
*   **Süre Ayarları**:
    *   Mevcut seçeneklere ek olarak **8-10 Saat Arası Rastgele** süre seçeneği.
*   **Format ve Kalite Standartları**:
    *   **Varsayılan Ayarlar**: AV1 Codec, 1080p, 60fps.
    *   **Ses Standardizasyonu**: Tüm ses kanallarının MP3 320k 48kHz formatına dönüştürülmesi ve orijinal dosyaların arşivlenmesi.
    *   **Hazır Modlar**: 'Basit' ve 'Orta' profil seçenekleri.

### Canlı Yayın Otomasyonu (YouTube Livestream)
*   **Otomatik Döngü**: Yayının 60-180 dakika aralığında içerik değiştirmesi.
*   **Çoklu Kanal Desteği**: Farklı kanallar için ayrı Intro/Loop video havuzları ve müzik klasörleri.
*   **Dinamik Yapılandırma**: Her kanal için 10 adet JSON konfigürasyon dosyası ile yayın akışının yönetilmesi.
*   **Akış Aktarımı**: `nc` (netcat) komutu ile yerel bilgisayardan VPS'e video akışı sağlanması.

## 3. Eksiklikler ve Geliştirme Önerileri

*   **TUI (Terminal Arayüzü) Güncellemesi**: Textual tabanlı arayüzün, yeni eklenen "Smart Batch" ve "Drive Upload" özelliklerini destekleyecek şekilde güncellenmesi gerekmektedir.
*   **Hata Toleransı (Resiliency)**: Uzun süren (8+ saat) render ve upload işlemleri sırasında olası ağ kesintileri için "kaldığı yerden devam et" (resume) veya otomatik yeniden deneme (retry) mekanizmaları kritik önem taşır.
*   **Kaynak Yönetimi**: AV1 kodlaması ve eş zamanlı upload işlemi yüksek CPU/RAM tüketebilir. Sunucu kaynaklarına göre işlem önceliklerinin (nice value) ayarlanması gerekebilir.
*   **Loglama ve Bildirim**: İşlemlerin durumu hakkında daha detaylı loglama ve kullanıcıya anlık bildirim (render bitti, upload başladı vb.) mekanizmaları eklenebilir.
