# Paris döviz/ATM fırsat araştırması — Aşama 2: veri kaynakları ve toplama

Bu klasör, depodaki Streamlit uygulamasından bağımsızdır; uygulama dosyalarına dokunmaz.

## Klasörler

| Yol | İçerik |
|---|---|
| `docs/source_registry.csv` | Kaynak envanteri (11 kaynak, durumlar) |
| `docs/manual_verification_template.csv` | Elle doğrulama şablonu |
| `docs/PHASE_02_REPORT.md` | Türkçe değerlendirme raporu |
| `scripts/` | Tekrar çalıştırılabilir indirme/test scriptleri |
| `data/raw/<kaynak>/<tarih>/` | Ham dosyalar (değiştirilmez) + her birinin `.meta.json` kaynak bilgisi |
| `data/profiles/` | İndirilen tabloların sütun/boşluk/örnek profili |
| `logs/collection_log.jsonl` | Her adımın durumu (Veri indirildi ve açıldı / Engellendi / Bulunamadı / Hata …) |
| `logs/access_check_<tarih>.csv` | Sunucu erişim testi |
| `tests/` | Ağdan bağımsız altyapı testleri |

## Kurulum ve çalıştırma

```bash
cd paris_market_research
pip install -r requirements.txt
python scripts/check_access.py          # önce erişim testi
python scripts/run_all.py --limit 100   # tüm kaynaklar (biri düşerse diğerleri sürer)
python -m unittest discover -s tests -v # altyapı testleri
```

Tek tek: `fetch_datagouv.py`, `fetch_apur_bdcom.py`, `fetch_osm_overpass.py`,
`fetch_insee_filosofi.py`, `fetch_opendatasoft.py`, `geocode_sample.py`, `fetch_reports.py`
(her biri `--help` ile açıklamasını gösterir). `--force` önbelleği yok sayar.

İsteğe bağlı: `CONTACT_EMAIL` ortam değişkeni User-Agent'a eklenir (dosyaya yazılmaz).

## Gerekli ağ erişimi

`www.data.gouv.fr`, `static.data.gouv.fr`, `www.apur.org`, `opendata.apur.org`,
`services*.arcgis.com` / `*.arcgis.com`, `overpass-api.de`, `wiki.openstreetmap.org`,
`taginfo.openstreetmap.org`, `www.insee.fr`, `data.geopf.fr`, `ressources.data.sncf.com`,
`data.iledefrance-mobilites.fr`, `opendata.paris.fr`, `www.banque-france.fr`, `parisjetaime.com`.
