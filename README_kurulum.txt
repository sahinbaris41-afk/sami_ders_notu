LEKSIKOGRAF v18 KURULUM REHBERI

Bu surum yerel calisir.
API anahtari gerekmez.

1. GEREKENLER
- Windows 10 veya 11
- Python 3.10 veya uzeri
- Tesseract OCR
- Internet baglantisi
  Ilk kurulumda Python paketleri indirilecegi icin gerekir.

2. PYTHON KONTROLU
- Komut Istemi veya PowerShell acin.
- Su komutlardan birini deneyin:
  python --version
  veya
  py -3 --version

Python bulunmuyorsa once Python kurun.

3. TESSERACT KURULUMU
- Tesseract OCR kurulu olmadan OCR ozelligi calismaz.
- Indirme adresi:
  https://github.com/tesseract-ocr/tesseract
- Windows icin yaygin kurulum yolu:
  C:\Program Files\Tesseract-OCR\tesseract.exe

Uygulama bu yolu otomatik kontrol eder.
Farkli bir yere kurduysaniz TESSERACT_CMD ortam degiskeni tanimlayabilirsiniz.

4. UYGULAMAYI BASLATMA
- Proje klasorune gidin:
  C:\el_yazisi_tanıma
- run_local.bat dosyasini cift tiklayin
  veya terminalden su sekilde calistirin:
  run_local.bat

Bu betik sunlari yapar:
- .venv sanal ortamini olusturur
- pip gunceller
- requirements.txt paketlerini kurar
- Streamlit uygulamasini baslatir

5. ILK CALISMA SONRASI
- Tarayicida Streamlit sayfasi acilacaktir.
- Sol panelden not arsiv klasorunu kontrol edin.
- Profesyonel OCR sekmesinden not gorsellerinizi yukleyin.
- PDF araclari icin data klasorundeki mufredat PDF'ini kullanabilirsiniz.

6. SORUN GIDERME

Python bulunamadi:
- Python'i kurun.
- Kurulumda "Add Python to PATH" secenegini acin.

Paket kurulumu basarisiz:
- Internet baglantinizi kontrol edin.
- Kurumsal ag kullaniyorsaniz pip erisimi engellenmis olabilir.

OCR metni cikmiyor:
- Tesseract'in kurulu oldugunu kontrol edin.
- Defter fotografini daha aydinlik ve duz cekin.

Streamlit acilmiyor:
- Terminalde hata varsa once onu kontrol edin.
- Gerekirse .venv klasorunu silip run_local.bat dosyasini tekrar calistirin.

7. ONEMLI NOT
- Bu surumde OpenAI veya Gemini kullanimi yoktur.
- Gercek API anahtari saklanmaz.
- Notlar yerel olarak notes_archive klasorune kaydedilir.
