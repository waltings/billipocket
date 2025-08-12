# BilliPocket - Ettevõtte Arvehaldussüsteem

**Port:** 5010 | **Eesti keel** | **Flask + SQLite**

BilliPocket on kerge ja töökindel arvehaldussüsteem väikesele ettevõttele, mis pakub kiiret viisi klientide ning arvete haldamiseks koos PDF genereerimisega.

## 🚀 Kiirstart

### Eeldused
- Python 3.10+
- macOS/Linux (soovituslik)
- WeasyPrint süsteemiraamatukogud

### macOS paigaldus
```bash
# WeasyPrint sõltuvused
brew install cairo pango gdk-pixbuf libffi

# Projekt
cd billipocket_gpt5
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Andmebaasi häälestus
```bash
export FLASK_APP=run.py
flask init-db           # Loo tabelid
flask init-vat-rates    # Loo Eesti KM määrad
flask seed-data         # Lisa demoandmed
```

### Käivitamine
```bash
python run.py
```

Ava brauseris: **http://127.0.0.1:5010/**

---

## 📋 Põhifunktsioonid

### Klientide haldus
- ✅ CRUD toimingud (loo, vaata, muuda, kustuta)
- ✅ Otsingufiltrid (nimi, e-mail, registrikood)
- ✅ Kliendi arvestatistika
- ✅ AJAX-toega vormid

### Arvete haldus
- ✅ Arve loomine dünaamiliste realiiidega
- ✅ Automaatne numeratsioon (`YYYY-####`)
- ✅ Staatuste haldus: `mustand` → `saadetud` → `makstud`
- ✅ Tähtaja jälgimine (`tähtaeg ületatud`)
- ✅ Eesti KM määrad (24%, 20%, 9%, 0%)

### PDF genereerimine
- ✅ 3 stiili: `standard`, `modern`, `elegant`
- ✅ A4 formaat WeasyPrintiga
- ✅ URL: `/invoice/<id>/pdf?style=modern`
- ✅ Ettevõtte seadete integratsioon

### Armatuurlaud
- ✅ Kuu käive ja laekumised
- ✅ Maksmata arvete statistika
- ✅ Keskmine makseaeg
- ✅ 12 kuu tulude graafik

---

## 🏗️ Tehniline arhitektuur

### Stack
- **Backend:** Flask 3.0+, SQLAlchemy, Blueprint-põhine
- **Database:** SQLite (dev), PostgreSQL-ready
- **Frontend:** Jinja2, Bootstrap 5, Chart.js
- **PDF:** WeasyPrint (A4 täistugi)
- **Security:** Flask-WTF CSRF

### Projektstruktuur
```
billipocket_gpt5/
├─ app/
│  ├─ __init__.py              # App factory
│  ├─ config.py                # Env-based config
│  ├─ models.py                # SQLAlchemy mudelid
│  ├─ forms.py                 # Flask-WTF vormid
│  ├─ logging_config.py        # Logi seadistus
│  ├─ routes/                  # Blueprint marsruudid
│  │  ├─ dashboard.py          # Ülevaade ja seaded
│  │  ├─ clients.py            # Klientide haldus
│  │  ├─ invoices.py           # Arvehaldus
│  │  └─ pdf.py                # PDF genereerimine
│  └─ services/                # Äriloogika
│     ├─ numbering.py          # Arvenumbrite teenus
│     ├─ totals.py             # Kogusummade arvutus
│     └─ status_transitions.py # Staatuste haldus
├─ templates/                  # Jinja2 mallid
│  ├─ pdf/                     # PDF mallid (3 stiili)
│  └─ *.html                   # Veebi UI
├─ static/                     # CSS/JS/pildid
├─ tests/                      # Pytest testid
├─ run.py                      # Käivitusskript
└─ requirements.txt            # Sõltuvused
```

---

## 🛠️ CLI käsud

```bash
# Andmebaasi haldus
flask init-db                  # Loo tabelid
flask seed-data                # Lisa demoandmed
flask init-vat-rates           # Loo Eesti KM määrad

# Haldus
flask create-admin <nimi> <email>  # Tuleviku admin kasutaja
flask update-overdue           # Uuenda tähtaja ületanud arved

# Keskkonna seadistus
export FLASK_ENV=development   # või production
export SECRET_KEY=your-key
export DATABASE_URL=sqlite:///billipocket.db
```

---

## 🧪 Testimine

### Pytest käivitamine
```bash
# Kõik testid
pytest -q

# Katvuse raport
pytest --cov=app --cov-report=term-missing

# Spetsiifilised testid
python tests/run_tests.py --unit --coverage
python tests/run_tests.py --integration --verbose
python tests/run_tests.py --estonian  # Estonian business rules
```

### Test kategoriad
- **Unit testid:** Mudelid, teenused, vormid
- **Integration testid:** Täielikud töövood
- **Route testid:** Blueprint-id, autentimine
- **Estonian compliance:** KM süsteem, ärireeglid

---

## 📊 KM (VAT) süsteem

### Eesti määrad
- **24%** - Standardmäär (vaikimisi)
- **20%** - Vähendatud määr
- **9%** - Vähendatud määr
- **0%** - Käibemaksuvaba

### Kasutamine
```python
# Koodis
vat_rates = VatRate.get_active_rates()
default_rate = VatRate.get_default_rate()  # 24%

# CLI
flask init-vat-rates  # Automaatne seadistus
```

---

## 🚀 Deploy (Production)

### Apache mod_wsgi
```python
# wsgi.py
from app import create_app
application = create_app('production')
```

### Gunicorn
```bash
gunicorn -w 2 -b 127.0.0.1:5010 wsgi:application
```

### Keskkonnmuutujad
```bash
export FLASK_ENV=production
export SECRET_KEY="your-production-secret"
export DATABASE_URL="postgresql://user:pass@localhost/billipocket"
```

---

## 🔧 Seadistamine

### Company Settings
- Ettevõtte info (nimi, aadress, registrikood)
- Vaikimisi KM määr ja PDF mall
- Logo URL ja arvetingimused

### PDF mallid
- **Standard:** Klassikaline äridokument
- **Modern:** Nüüdisaegne disain
- **Elegant:** Peenelt kujundatud

Mallide muutmine: `templates/pdf/invoice_*.html`

---

## 🐛 Veaotsing (FAQ)

**Port 5010 kasutusel?**
```bash
python run.py --port 5011
```

**WeasyPrint error?**
```bash
# macOS
brew install cairo pango gdk-pixbuf libffi

# Ubuntu/Debian
apt-get install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0
```

**SQLite "permission denied"?**
- Kontrolli failiõiguseid projektikaustas
- Andmebaas: `instance/billipocket.db`

**CSRF token missing?**
- Kontrolli `SECRET_KEY` seadistust
- Vormides peab olema `{{ form.csrf_token }}`

---

## 📚 Dokumentatsioon

Täielik dokumentatsioon: [`Billipocket_Documentation.md`](./Billipocket_Documentation.md)

### Arendajatele
- **Blueprintid:** Loogiline jaotus (dashboard/clients/invoices/pdf)
- **Teenused:** Äriloogika eraldi (`services/` kaust)
- **Vormid:** Flask-WTF + CSRF + server valideerimine
- **Logid:** Rotatsiooniga failid (`logs/` kaust)

---

## 🤝 Panustamine

1. Fork projekt
2. Loo feature branch (`git checkout -b feature/amazing-feature`)
3. Commit muudatused (`git commit -m 'Add amazing feature'`)
4. Push branch'i (`git push origin feature/amazing-feature`)
5. Ava Pull Request

---

## 📄 Litsents

See projekt on väikesele ettevõttele kavandatud kergekaaluline arvehaldussüsteem.