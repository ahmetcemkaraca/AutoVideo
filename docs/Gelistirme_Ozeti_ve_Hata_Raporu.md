# Geliştirme Özeti ve Hata Raporu

Bu belge, son geliştirme oturumunda yapılan değişiklikleri, eklenen özellikleri ve tespit edilen durumları özetler.

## 1. Yeni Eklenen Özellikler

### ✨ Smart Batch (Akıllı Toplu İşlem)
*   **Otomatik Tespit:** Klasördeki `*_intro.mp4` ve `*_loop.mp4` dosyalarını otomatik eşleştiren `SmartBatchDetector` modülü eklendi. Artık manuel dosya seçimi yapmadan toplu iş listesi oluşturulabiliyor.
*   **Sihirbaz Arayüzü (Wizard):** Tespit edilen çiftleri listeleyen, onaylayan ve genel ayarları (Süre, Codec, Müzik Modu) yapılandıran `SmartBatchScreen` arayüzü geliştirildi.
*   **Özelleştirme:** "Her projeyi ayrı ayrı özelleştir" seçeneği ile her video çifti için farklı müzik veya ayar girebilme altyapısı kuruldu.

### 🚀 Encoding Optimizasyonu (Smart Skipping)
*   **Mantık:** Render motoruna (`VideoEncoder`), kaynak videonun hedef ayarlar ile uyumlu olup olmadığını kontrol eden `is_compatible` fonksiyonu eklendi.
*   **İşleyiş:** Eğer kaynak video (Intro veya Loop) halihazırda istenen çözünürlük, codec (H264/AV1/HEVC), FPS ve pixel formatındaysa, yeniden encode edilmez. Bunun yerine doğrudan dosya kopyalanır (`shutil.copy2`).
*   **Fayda:** Uyumlu dosyalarda işlem süresini dakikalardan saniyelere düşürür.

### 📡 VPS Deployment Araçları
*   **Amaç:** Geliştirilen kodun VPS sunucusuna hızlıca gönderilmesi.
*   **Araç 1 (Python):** `scripts/send_to_vps.py` - Projeyi hafızada zipleyip TCP üzerinden gönderir.
*   **Araç 2 (PowerShell - İstenen Yöntem):** `scripts/send_to_vps.ps1` - Python veya Zip bağımlılığı olmadan, `tar` komutunu doğrudan `nc` (netcat) aracına pipe ederek gönderim sağlar.
*   **Filtreleme:** `mp4`, `mkv` gibi büyük medya dosyaları ve `.git`, `__pycache__` gibi gereksiz klasörler transferden otomatik olarak hariç tutulur.

## 2. İyileştirmeler ve Düzeltmeler

*   **Ses Karıştırma (Audio Mixing):** Kullanıcı talebi üzerine background seslerin sıralı değil, **aynı anda (simultane)** çalması gerektiği teyit edildi. `audio.py` içerisindeki `mix_tracks` fonksiyonunun `amix` filtresi kullanarak bunu zaten doğru yaptığı doğrulandı.
*   **Job Status Fix:** Smart Batch ekranında işlerin `RUNNING` (Çalışıyor) olarak değil, doğru şekilde `QUEUED` (Sırada) olarak eklenmesi sağlandı.

## 3. Notlar ve Öneriler

*   **nc (Netcat) Gereksinimi:** PowerShell deployment scriptinin çalışması için Windows makinede `nc` komutunun yüklü ve PATH'e ekli olması gerekmektedir.
*   **Müzik Seçimi:** Smart Batch sihirbazında "Fixed" müzik seçimi şu an basitleştirilmiş durumdadır, ileride tam dosya gezgini ile geliştirilebilir.
