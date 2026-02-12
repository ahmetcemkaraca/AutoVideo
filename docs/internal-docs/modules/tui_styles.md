# TUI Styles (styles.tcss)

Video Renderer TUI uygulaması için Textual CSS stil dosyası.

## Dosya Konumları

| Paket | Dosya Yolu |
|-------|------------|
| Ana Renderer | `video_renderer/styles.tcss` |
| RAM Test | `video_renderer_ramtest/styles.tcss` |

---

## Renk Paleti (Color Palette)

### Temel Renkler

| Değişken | Hex Kodu | Kullanım |
|----------|----------|----------|
| `$primary` | `#00d4ff` | Ana vurgu rengi (cyan) |
| `$secondary` | `#ff00ff` | İkincil vurgu rengi (magenta) |
| `$success` | `#00ff88` | Başarı durumu (yeşil) |
| `$warning` | `#ffaa00` | Uyarı durumu (turuncu) |
| `$error` | `#ff4444` | Hata durumu (kırmızı) |

### Yüzey Renkleri

| Değişken | Hex Kodu | Kullanım |
|----------|----------|----------|
| `$surface` | `#1a1a2e` | Ana yüzey arka planı |
| `$surface-dark` | `#0f0f1a` | Koyu arka plan (ekran, log) |
| `$surface-light` | `#252540` | Açık yüzey (input, hover) |

### Metin Renkleri

| Değişken | Hex Kodu | Kullanım |
|----------|----------|----------|
| `$text` | `#e0e0e0` | Ana metin rengi |
| `$muted` | `#888888` | Soluk metin (etiketler, altyazılar) |

### Mod-Specific Renkler (Sadece Ana Renderer)

| Değişken | Hex Kodu | Kullanım |
|----------|----------|----------|
| `$ram-color` | `#ff6600` | RAM modu vurgusu |
| `$ramdisk-color` | `#ff9900` | RAMDisk modu vurgusu |
| `$vram-color` | `#00ff66` | VRAM modu vurgusu |

---

## Bileşen Stilleri

### 1. Screen (Ekran)

```css
Screen {
    background: $surface-dark;
    align: center middle;
}
```

**Açıklama**: Tüm ekranların varsayılan arka planı ve hizalaması.

---

### 2. Header & Footer

| Bileşen | Arka Plan | Metin Rengi | Stil |
|---------|-----------|-------------|------|
| `Header` | `$surface` | `$primary` | bold |
| `Footer` | `$surface` | `$muted` | normal |

---

### 3. Container Sınıfları

#### `.container`
Genel içerik kapsayıcısı.
- `width: 100%`
- `height: auto`
- `padding: 1 2`

#### `.center-container`
Ortalanmış içerik için.
- `align: center middle`
- `width: 100%`
- `height: 100%`

#### `.main-wrapper` (Ana Renderer)
Ortalanmış ana içerik sarmalayıcısı.
- `width: 100%`
- `max-width: 120`
- `height: 100%`
- `align: center top`

#### `.main-content` (RAM Test)
Kaydırılabilir ana içerik alanı.
- `width: 100%`
- `height: 1fr`
- `overflow-y: auto`
- `scrollbar-color: $primary`

---

### 4. Panel Sınıfları

#### `.panel`
Standart panel kutusu.
```css
.panel {
    background: $surface;
    border: round $primary;
    padding: 1 2;
    margin: 1 2;
}
```

#### `.panel-title`
Panel başlığı.
- `color: $primary`
- `text-style: bold`
- `text-align: center`

#### `.mode-panel` (Ana Renderer)
Mod seçimi paneli.
- `background: $surface-light`
- `border: round $ram-color`

#### `.memory-panel` (Ana Renderer)
Bellek ayarları paneli.
- `background: $surface-light`
- `border: round $vram-color`

---

### 5. Button Stilleri

#### Varsayılan Button
```css
Button {
    margin: 1 2;
    min-width: 20;
}
```

#### Button Varyantları

| Sınıf | Arka Plan | Metin | Kullanım |
|-------|-----------|-------|----------|
| `.-primary` | `$primary` | `$surface-dark` | Ana aksiyonlar |
| `.-secondary` | `$surface-light` | `$text` | İkincil aksiyonlar |
| `.-success` | `$success` | `$surface-dark` | Onay işlemleri |
| `.-error` | `$error` | `white` | İptal/silme işlemleri |

#### Hover/Focus Davranışı
```css
Button.-primary:hover { background: #33ddff; }
Button.-primary:focus { background: #66eeff; }
Button.-secondary:hover {
    background: $surface;
    border: solid $primary;
}
```

#### `.hidden`
Gizli butonlar için `display: none`.

---

### 6. DataTable Stilleri

```css
DataTable {
    background: $surface;
    scrollbar-background: $surface-dark;
    scrollbar-color: $primary;
}
```

| Alt Eleman | Açıklama |
|------------|----------|
| `.datatable--header` | Tablo başlığı (surface-light arka plan, primary metin) |
| `.datatable--cursor` | Seçili satır (primary 20% opacity) |
| `.datatable--hover` | Hover edilen satır (surface-light) |

---

### 7. ProgressBar Stilleri

```css
ProgressBar {
    padding: 0 1;
}

ProgressBar > .bar--bar {
    color: $primary;
    background: $surface-light;
}

ProgressBar > .bar--complete {
    color: $success;
}
```

#### Progress Container
```css
.progress-container {
    margin: 1 0;
    padding: 1;
    background: $surface;
    border: round $muted;
}
```

#### Progress Durum Etiketleri

| Sınıf | Renk | Kullanım |
|-------|------|----------|
| `.progress-complete` | `$success` | Tamamlanan işlemler |
| `.progress-pending` | `$muted` | Bekleyen işlemler |
| `.progress-active` | `$primary` (bold) | Aktif işlemler |

---

### 8. Input Stilleri

```css
Input {
    background: $surface-light;
    border: tall $muted;
    padding: 0 1;
}

Input:focus {
    border: tall $primary;
}
```

---

### 9. RadioSet & Select

#### RadioSet
```css
RadioSet {
    background: transparent;
    border: none;
    padding: 0 1;
}

RadioButton:focus {
    background: $surface-light;
}
```

#### Select
```css
Select {
    background: $surface-light;
    border: tall $muted;
}

Select:focus {
    border: tall $primary;
}
```

---

### 10. Label & Text Sınıfları

#### Başlık Sınıfları

| Sınıf | Renk | Stil | Kullanım |
|-------|------|------|----------|
| `.title` | `$primary` | bold, center | Ana başlıklar |
| `.subtitle` | `$muted` | center | Alt başlıklar |
| `.banner-text` | `$secondary` | bold | Banner metinleri |

#### Durum Metinleri

| Sınıf | Renk | Kullanım |
|-------|------|----------|
| `.success-text` | `$success` | Başarı mesajları |
| `.error-text` | `$error` | Hata mesajları |
| `.warning-text` | `$warning` | Uyarı mesajları |
| `.info-text` | `$primary` | Bilgi mesajları |

#### Codec Etiketleri

| Sınıf | Renk | Codec |
|-------|------|-------|
| `.codec-av1` | `$success` | AV1 |
| `.codec-h265` | `$primary` | H.265/HEVC |
| `.codec-h264` | `$warning` | H.264/AVC |

#### Durum Etiketleri

```css
.status-label {
    margin-left: 2;
    color: $muted;
    text-style: bold;
    content-align: center middle;
    padding: 1 2;
    background: $surface-light;
    border: none;
}

.status-label.-active {
    color: $surface-dark;
    background: $success;
}
```

---

### 11. Validation Screen Stilleri (Ana Renderer)

| Sınıf | Arka Plan | Metin | Kullanım |
|-------|-----------|-------|----------|
| `.status-pass` | `$success` | `$surface-dark` | Doğrulama başarılı |
| `.status-fail` | `$error` | `white` | Doğrulama başarısız |
| `.status-warning` | `$warning` | `$surface-dark` | Doğrulama uyarısı |

---

### 12. Log Panel

```css
.log-panel {
    background: $surface-dark;
    border: round $muted;
    height: auto;
    max-height: 10;
    padding: 0 1;
    overflow-y: auto;
}
```

| Log Satırı Sınıfı | Renk |
|-------------------|------|
| `.log-line` | `$muted` |
| `.log-line-error` | `$error` |
| `.log-line-success` | `$success` |

---

### 13. Summary Panel

```css
.summary-row {
    layout: horizontal;
    height: 1;
    padding: 0 1;
}

.summary-label {
    color: $muted;
    width: 15;
}

.summary-value {
    color: $text;
    text-style: bold;
}
```

---

### 14. Status Bar

```css
.status-bar {
    dock: bottom;
    height: 1;
    background: $surface;
    padding: 0 1;
}

.status-text {
    color: $muted;
}
```

---

### 15. Action Bar

```css
.action-bar {
    height: auto;           /* RAM Test: height: 3 */
    min-height: 3;          /* Sadece Ana Renderer */
    layout: horizontal;
    align: center middle;
    padding: 1 2;           /* RAM Test: padding: 0 2 */
    background: $surface;
    margin-top: 1;          /* Sadece Ana Renderer */
    /* RAM Test'te ekstra: border-top: solid $muted */
}
```

---

### 16. Banner (Home Screen)

```css
.banner {
    width: 100%;
    content-align: center middle;
    padding: 2 0;
}

.banner-text {
    color: $secondary;
    text-style: bold;
}
```

---

### 17. Button Row (RAM Test)

```css
.button-row {
    height: auto;
    width: 100%;
    align: center middle;
    margin-top: 1;
}
```

---

### 18. Top Shortcuts (RAM Test)

```css
.top-shortcuts {
    width: 100%;
    height: 1;
    background: $surface;
    color: $primary;
    text-align: center;
    text-style: bold;
    border-bottom: solid $muted;
}
```

---

### 19. Upload Row

```css
.upload-row {
    height: auto;
    align: center middle;
    margin-bottom: 1;
}
```

---

### 20. Hidden (Gizli Elemanlar)

```css
.hidden {
    display: none;
}
```

---

## İki Versiyon Arasındaki Farklar

### Ana Renderer (`video_renderer/styles.tcss`) Ekstra Özellikleri:

1. **Mode-Specific Renkler**: `$ram-color`, `$ramdisk-color`, `$vram-color`
2. **Mode Panel Sınıfları**: `.mode-panel`, `.mode-option`, `.memory-panel`
3. **Main Wrapper**: `.main-wrapper` (max-width: 120)
4. **Validation Stilleri**: `.status-pass`, `.status-fail`, `.status-warning`
5. **Action Bar**: `min-height: 3`, `margin-top: 1`

### RAM Test (`video_renderer_ramtest/styles.tcss`) Ekstra Özellikleri:

1. **Main Content**: `.main-content` (scrollable, height: 1fr)
2. **Button Row**: `.button-row`
3. **Top Shortcuts**: `.top-shortcuts`
4. **Action Bar**: `height: 3`, `border-top: solid $muted`
5. **Screen Layout**: `layout: vertical` ekli

---

## Kullanım Örnekleri

### Python'da Kullanım

```python
from textual.app import App
from textual.widgets import Button, Header, Footer

class MyApp(App):
    CSS_PATH = "styles.tcss"

    def compose(self):
        yield Header()
        yield Button("Primary Action", classes="-primary")
        yield Button("Secondary Action", classes="-secondary")
        yield Footer()
```

### Widget'a Sınıf Ekleme

```python
# Buton varyantları
Button("Save", classes="-primary")
Button("Cancel", classes="-secondary")
Button("Delete", classes="-error")

# Durum metinleri
Static("Success!", classes="success-text")
Static("Error occurred", classes="error-text")

# Codec etiketleri
Static("AV1", classes="codec-av1")
Static("H.265", classes="codec-h265")
```

---

## Textual CSS Notları

- **Değişkenler**: `$variable` syntax ile tanımlanır
- **Birimler**: `1` = 1 karakter, `2` = 2 karakter genişliği
- **Renkler**: Hex (`#00d4ff`) veya yüzde opacity (`$primary 20%`)
- **Border Tipleri**: `round`, `solid`, `tall`, `wide`
- **Layout**: `horizontal`, `vertical`
- **Align**: `center`, `middle`, `top`, `bottom`

---

## İlgili Dosyalar

- [TUI Screens](./tui_screens.md) - Ekran implementasyonları
- [Textual Documentation](https://textual.textualize.io/css/) - Resmi Textual CSS dokümantasyonu
