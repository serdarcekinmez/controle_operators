# Aşama 2 — Veri kaynakları ve toplama yöntemi: değerlendirme

Tarih: 2026-10-07 · Kapsam: Paris'in 20 arrondissement'ı (tampon tasarımı açık bırakıldı)

## 0. Önce bilinmesi gereken: bu çalıştırmada veri indirilemedi

Çalışma, ağ erişimi kısıtlı bir bulut ortamında yapıldı. Ortamın ağ politikası,
bu projede gereken **bütün** kaynak sunucularını engelledi. Proxy her bağlantıyı
`403 Forbidden (connect_rejected)` ile reddetti:

- `scripts/check_access.py`: 15 uç noktanın 15'i **Engellendi** (`logs/access_check_2026-10-07.csv`).
- `scripts/run_all.py`: 32 log satırı; 30 indirme adımının hepsi **Engellendi**, 2 özet adımı veri olmadığı için **Atlandı** (`logs/collection_log.jsonl`).
- Sayfa getirme aracı (WebFetch) da aynı alan adlarında engellendi.
- Yalnızca **web araması** çalıştı. Bu araç kaynak sayfalarını açmıyor, yalnızca arama
  sonuçlarının kısa özetini döndürüyor.

Sonuç olarak:

- **Hiçbir kaynak için “Veri indirildi ve açıldı” veya “Dokümantasyon doğrulandı” durumu verilmedi.**
- Envanterdeki “Bulundu” durumu yalnızca şunu söyler: kaynak sayfası web aramasında
  güncel olarak listeleniyor. Sayfa içeriği, alanlar, lisans ve indirme bağlantıları
  **doğrulanmadı**.
- Arama özetinden gelen bilgiler raporda ve envanterde “arama özeti; doğrulanmadı”
  olarak işaretlendi.
- `data/raw/` bilerek boş. Engellenen isteklerin yerine sahte veya tahmini dosya konmadı.

**Bu engeli kaldırmak için:** ortam ayarlarında *Network access* bölümüne
README'deki alan adları eklenmeli ya da daha geniş bir erişim düzeyi seçilmeli.
Alternatif olarak scriptler internet erişimi olan herhangi bir makinede aynen
çalıştırılabilir (`python scripts/run_all.py`). Scriptler bu iş için yazıldı:
bağlantılar elle sabitlenmedi, her çalıştırmada kaynağın API'sinden veya
sayfasından çözülüyor.

## 1. Hangi verilere fiilen erişebildik?

**Hiçbirine.** Hiçbir kaynaktan veri dosyası indirilip açılamadı.

Gerçekten çalıştırılıp doğrulanan şeyler şunlar:

| Kontrol | Sonuç |
|---|---|
| 15 uç noktaya erişim testi (`check_access.py`) | Çalıştı; 15/15 Engellendi |
| Tüm toplama zinciri (`run_all.py`) | Çöküş olmadan bitti. Her engel kaynak ve adım bazında loglandı, boş veya sahte çıktı yazılmadı. |
| Altyapı testleri (`tests/test_plumbing.py`, 7 test) | Hepsi geçti. Kapsam: yerel HTTP sunucusu üzerinden indirme, meta kaydı ve önbellek; *CSV beklerken HTML gelirse başarı sayılmaması*; 404'ün “Bulunamadı” olarak loglanması; OSM satır düzleştirme (eksik etiket boş kalır, “yok” yazılmaz); tampon için `--buffer-km` zorunluluğu; ArcGIS katman URL çözümü. |
| Overpass sorgu üretimi (`--print-queries`) | Sorgular üretildi ve gözle kontrol edildi. Overpass sunucusunda **çalıştırılmadı**. |

Web aramasından elde edilen ve **doğrulanması gereken** ipuçları:

- **Filosofi:** INSEE'nin 2022 sürümünü veri kalitesi nedeniyle üretmeyeceği yazıyor.
  Bu doğruysa 2021 IRIS sürümü en güncel IRIS sürümü olarak kalır.
- **BDCOM:** 2017, 2020 ve 2023 sürümleri var. 2023 sürümü Haziran 2023 saha sayımına
  dayanıyor ve 83 154 lokal içeriyor. Lisans ODbL; KML/CSV/GeoJSON/SHP ve GeoService
  olarak sunuluyor. Sayım 3 yılda bir yapıldığı için 2026 sürümünün yayımlanıp
  yayımlanmadığı kontrol edilmeli.
- **SNCF:** 2015–2024 yılları, yaklaşık 3 000 gar. İle-de-France bölgesel trafiği,
  3–4 yılda bir yapılan sayımlardan ekstrapole ediliyor.
- **IDFM:** Günlük ferré doğrulama verileri 2025'in 4. çeyreğine kadar listeleniyor.
  Saatlik profil alanları: `COD_STIF`, `CAT_JOUR`, `TRNC_HORR_60`, yüzde.
- **Banque de France:** fin-2025 raporu PDF olarak yayımlanmış
  (`/system/files/2026-07/2025_Rapport_Accessibilité.pdf`).
- **Géoplateforme geocoding:** Anahtar gerekmiyor; sınır IP başına yaklaşık 50 istek/sn.
- **Contours IRIS:** data.gouv'da son güncelleme 30/04/2026 görünüyor.

## 2. Hangileri API, hangileri toplu dosyayla alınmalı?

| Kaynak | Önerilen yöntem | Gerekçe |
|---|---|---|
| A Atout France | **Toplu CSV** (ulusal dosyanın tamamı). URL, data.gouv API'sinden çözülür. | Küçük dosya. API burada yalnızca güncel kaynak bağlantısını bulmak için kullanılır. |
| B APUR BDCOM | **API (ArcGIS FeatureServer)**: alan listesi, kod alanları ve örnek. Tam katman gerekirse toplu GeoJSON/CSV. | Faaliyet kodu sözlüğü katmanın meta verisinde olabilir. Filtreli sorgu da yapılabilir. |
| C OSM | **API (Overpass)**: kategori başına tam sayım ve ≤100 örnek. | Paris için tam çekim de küçük olur. Önce örnek, sonra tam çekim. |
| D Filosofi | **Toplu ZIP/CSV** | API'ye gerek yok. |
| E Contours IRIS | **Toplu arşiv** (büyük; `--download-large` ile) | Yalnızca Paris IRIS'leri ayıklanacak. |
| F1 SNCF | **Toplu CSV** (ODS dışa aktarım) | Yaklaşık 3 000 satır. |
| F2 IDFM | **API ile keşif ve örnek**, sonra dönem bazlı **toplu CSV** | Dönemsel çok sayıda veri seti var. Kimlikler katalogdan çözülmeli. |
| G Banque de France | **Yalnızca rapor/harita** (bekleniyor) | Adres düzeyinde DAB verisi veya API olarak sunulmamalı. |
| H Géoplateforme | **API** (yalnızca koordinatsız kayıtlar için) | Çok kayıt olursa `/search/csv` toplu uç noktası değerlendirilir (doğrulanacak). |
| I Paris je t'aime | **Yalnızca rapor** | Bağlam bilgisi; mahalle ölçümü değil. |
| J Paris arrondissements | **Toplu GeoJSON** | 20 poligon. Kapsam filtresi ve tampon tabanı için eklendi. |

## 3. Hangi bilgiler elle doğrulanmalı?

Kaynak düzeyinde (ağ açılınca ilk iş):

1. Her kaynağın lisansı, atıf metni ve güncel sürümü (envanterde “Doğrulanmadı” yazan alanlar).
2. Atout France dosyasında koordinat, oda ve kapasite sütunları gerçekten var mı?
3. BDCOM faaliyet kodu sözlüğü: döviz bürosu, seyahat acentesi, otel ve banka için ayrı
   kod var mı? **Kodlar tahmin edilmedi.** Script sözlükte yalnızca metin eşleşmesi
   arıyor; sonuç elle onaylanmalı.
4. Filosofi 2021 IRIS'in coğrafya yılı (“géographie au 1er janvier AAAA”) ve buna denk
   gelen Contours IRIS sürümü.
5. Filosofi 2022'nin gerçekten iptal edildiği ve 2021'den yeni bir IRIS sürümü
   olmadığı (INSEE sayfası).
6. IDFM bilet türü kodları ve gizlenen düşük hacimli istasyonlar.
7. Banque de France sayfasında indirilebilir tablo (XLSX/CSV) olup olmadığı.

İşletme düzeyinde (`docs/manual_verification_template.csv`):

- Döviz bürosu ile para transferi ayrımı (Western Union, Ria vb. ayrı kategori).
- Otomatik döviz makinesi varlığı. OSM'de bunun için yerleşik bir etiket yok; adaylar
  yalnızca ipucu.
- Yabancı para veren ATM'ler ve hangi para birimlerini verdikleri.
- Çalışma saatleri ve erişim koşulları (otel içi, istasyon içi, ücretli alan).
- Bankadaki `atm=yes` etiketi ile ayrı `amenity=atm` kaydının aynı makine olup olmadığı
  (çifte sayım).
- Otel oda sayısı ve yıldızı; seyahat acentelerinin gerçek faaliyeti.

Şablondaki satırlar yer tutucudur (`<işletme adı>`). Gerçek işletme bilgisi uydurulmadı.

## 4. Hangi kaynaklar eksik veya eski?

- **Filosofi:** Gelir yılı 2021. Arama özetine göre daha yeni bir IRIS sürümü
  olmayabilir. 2026 itibarıyla bu 5 yıllık bir gecikme demek.
- **BDCOM 2023:** Saha sayımı Haziran 2023'te yapıldı. Döviz bürosu gibi hızlı değişen
  işletmeler için eski olabilir. Ayrıca yalnızca vitrinli zemin kat lokalleri kapsıyor.
- **Atout France:** Yalnızca sınıflandırılmış tesisleri kapsıyor. Sınıfsız oteller ve
  kısa süreli kiralıklar yok.
- **OSM:** Güncel ama tamlığı bilinmiyor. `opening_hours` ve `currency:*` gibi etiketler
  büyük olasılıkla seyrek.
- **SNCF:** İle-de-France bölgesel trafiği ekstrapolasyon; yolcu sayısı turist sayısı
  değildir.
- **IDFM:** Doğrulama sayısı giriş sayısıdır; çıkışları, yayaları ve turist payını göstermez.
- **Yabancı para ATM'leri ve otomatik döviz makineleri için açık ve yapılandırılmış bir
  kaynak bulunamadı.** OSM etiketleri ve elle doğrulama gerekecek.
- **Turizm:** Mahalle düzeyinde açık bir ölçüm yok. Paris je t'aime verisi şehir ve
  Grand Paris geneli; bazı rakamlar Grand Paris kapsamında.

## 5. Yedi haritanın veri hazırlığı

| Harita | Ana kaynaklar | Hazırlık durumu |
|---|---|---|
| 1. Turizm | A (otel arzı, yıldız, kapasite), B (otel/acente), I (bağlam) | Script hazır, veri yok. Mahalle düzeyinde turist ölçümü yok; vekil gösterge (otel kapasitesi yoğunluğu) olarak tasarlanmalı. |
| 2. Ulaşım | F1 (yıllık gar yolcusu), F2 (istasyon doğrulamaları ve konumları) | Script hazır, veri yok. F1 ve F2 arasında gar eşleştirme tablosu gerekecek. |
| 3. Gelir | D (Filosofi IRIS) + E (konturlar) | Script hazır, veri yok. Coğrafya yılı uyumu doğrulanmalı. |
| 4. Rakipler | C (bureau_de_change, money_transfer ayrı), B (faaliyet kodları) | Script hazır, veri yok. BDCOM kod sözlüğü ve elle doğrulama kritik. |
| 5. ATM'ler | C (atm, atm=yes, currency:*), G (yalnızca bağlam) | Script hazır, veri yok. Çifte sayım ve yabancı para bilgisi zayıf olacak. |
| 6. Çalışma saatleri | C (`opening_hours`), F2 (saatlik profil) | Script hazır, veri yok. OSM saat alanı büyük olasılıkla seyrek; elle doğrulama gerekir. |
| 7. Fırsat bölgeleri | 1–6'nın bileşimi | Bu aşamada üretilmedi (kapsam dışı). Önce 1–6'nın veri durumu netleşmeli. |

## 6. Üçüncü aşamada gereken temizlik ve eşleştirmeler

1. **Kapsam:** J ile arrondissement atama yapılmalı; tampon genişliği gerekçeyle
   seçilmeli (OSM scripti `--buffer-km` ile hazır).
2. **Kod uyumu:** Paris = 75056 (komün), 75101–75120 (arrondissement INSEE),
   75001–75020 ve 75116 (posta kodu). IRIS kodları `751…` ile başlar.
3. **Koordinat sistemi:** Lambert-93 (EPSG:2154) ve WGS84 (EPSG:4326) arasında
   dönüşüm; koordinatların makullük kontrolü.
4. **Adres normalizasyonu ve geocoding:** Yalnızca koordinatı olmayan kayıtlar için;
   skor eşiği belirlenmeli.
5. **Kaynaklar arası eşleştirme:**
   - Otel: A ↔ B ↔ OSM (ad + adres + mesafe).
   - Döviz bürosu: OSM ↔ BDCOM.
   - Gar: SNCF ↔ IDFM.
6. **Çifte sayımı giderme:** Bankadaki `atm=yes` ile yakındaki `amenity=atm` kaydı
   (örneğin 30–50 m eşiği; eşik test edilmeli).
7. **Kategori ayrımı:** Döviz bürosu / otomatik döviz makinesi / kartlı ATM / yabancı
   para ATM'si / para transferi / otel / seyahat acentesi ayrı tutulmalı.
8. **Eksik bilgi:** Eksik değerler “bilinmiyor” olarak kodlanmalı, “hizmet yok” olarak
   değil.
9. **Saat verisi:** `opening_hours` ayrıştırılmalı; IDFM `CAT_JOUR`/`TRNC_HORR_60`
   profilleri normalize edilmeli.
10. **Veri yılları:** Her katmanda veri yılı ve çekim tarihi saklanmalı; farklı yıllar
    haritada belirtilmeli.
