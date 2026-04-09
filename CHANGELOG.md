# Changelog

Bu dosya projedeki onemli degisiklikleri surum bazli olarak takip eder.

## [v1.0.0] - 2026-04-09

### Eklendi
- `LEKSIKOGRAF v18` ana uygulamasi moduler paket yapisina tasindi.
- `leksikograf/ocr.py` ile yerel OCR akisi sade ve tekrar kullanilabilir hale getirildi.
- `leksikograf/academic.py` icine BTU UTL akademik kadro, bolum ozeti ve yayin toplama katmani eklendi.
- Akademik yayinlar icin yerel JSON onbellek destegi eklendi.
- Ders ve konu bazli yayin indeksleme ve onerme sistemi eklendi.
- Otomatik okuma listesi, sinav haftasi oncelikli ilk 5 yayin, gunluk plan ve 30/60/90 dakika modlari eklendi.
- `Vize Haftasi`, `Final Haftasi` ve `Son 3 Gun Panik Modu` stratejileri eklendi.
- `leksikograf/progress.py` ile ilerleme takibi, telafi plani ve haftalik basari raporu eklendi.
- `run_local.bat`, `requirements.txt` ve `README_kurulum.txt` ile yerel kurulum akisi netlestirildi.
- Temsili arayuz gorselleri ve kapsamli proje anlatimi iceren `README.md` eklendi.

### Degisti
- Ana uygulama API anahtari ve uzak LLM bagimliligindan arindirildi.
- Akademik Kadro sekmesi, resmi BTU kaynaklarindan veri cekebilen ve onbellekten calisabilen yeni yapiya tasindi.
- Yayin arama mantigi hoca bazli listeden konu bazli tavsiye motoruna genisletildi.

### Guvenlik
- Test ve uygulama dosyalarindaki API key kullanimi kaldirildi.
- Yerel dosya tabanli, API'siz kullanim modeli varsayilan hale getirildi.

### Notlar
- Bu surum, deponun profesyonel README, changelog ve ilk resmi surum etiketi ile sunulan ilk kapsamli yayinidir.
