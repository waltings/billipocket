# Billipocket – detailne dokumentatsioon

Viimane uuendus: 2025-08-10
Vaikimisi port: **5010**

---

## 1. Ülevaade

Billipocket on kerge **arvehaldussüsteem** (Flask + Jinja2 + SQLite + WeasyPrint), mille eesmärk on pakkuda väikesele ettevõttele kiiret ja töökindlat viisi klientide ning arvete haldamiseks. UI on **eesti keeles**, paigutus on **mobiilisõbralik** ning fookuses on **lihtsus, turvalisus ja loetavus**.

**Põhifunktsioonid (eesmärgid):**
- Kliendid: loomine, muutmine, kustutamine, otsing ja filtreerimine.
- Arved: loomine (dünaamilised realiinid), muutmine, kustutamine, staatuste vahetus (mustand → saadetud → makstud), filtreerimine.
- Arvenumber: automaatne jooksev numeratsioon formaadis `YYYY-####`.
- PDF: arve PDF (A4), stiilivalikud (`standard`, `modern`, `elegant`) parameetriga `?style=`.
- Armatuurlaud: kuu käive, laekumised, maksmata arvete arv, keskmine makseaeg, 12 kuu graafik.
- Turvalisus: CSRF kõigil vormidel, sisendi valideerimine nii kliendis kui serveris.
- CLI: `flask init-db`, `flask seed-data`, `flask create-admin` (tulevikuks).

**Praegune seis (skeleton):**
- Valmis baasmallid, navigeerimine, tabelid ja PDF-i põhidemo WeasyPrintiga.
- Port on 5010 (dev server).

**Soovitus laienduseks (Claude Code agentidele):**
- Teha täis-CRUD, SQLAlchemy mudelid ja vormid, nummerdus- ja kogusummade teenused, 3 PDF-stiili ning testikomplekt (vt peatükke 7–11).

---

## 2. Tehniline arhitektuur

**Stack:** Flask (Jinja2), SQLite, SQLAlchemy (soovitus), Flask-WTF, WeasyPrint, Bootstrap 5, Chart.js.

**Soovitatav kaustastruktuur (sihtarhitektuur):**
```
billipocket_gpt5/
├─ app/
│  ├─ __init__.py            # app factory, db, CSRF, blueprintide registreerimine
│  ├─ config.py              # Development/Production seadistused
│  ├─ models.py              # SQLAlchemy mudelid (Client, Invoice, InvoiceLine)
│  ├─ forms.py               # Flask-WTF vormid ja valideerimine
│  ├─ routes/
│  │  ├─ dashboard.py        # avalehe näitajad ja graafik
│  │  ├─ clients.py          # kliendihaldus
│  │  ├─ invoices.py         # arvehaldused (sh realiinid, staatuse muutused)
│  │  └─ pdf.py              # PDF renderdus (WeasyPrint)
│  ├─ services/
│  │  ├─ numbering.py        # arvenumbri genereerimine (YYYY-####)
│  │  └─ totals.py           # vahesumma, KM, kogusumma arvutus
│  ├─ templates/
│  │  ├─ layout.html
│  │  ├─ overview.html
│  │  ├─ clients.html
│  │  ├─ invoices.html
│  │  ├─ invoice_form.html
│  │  ├─ 404.html
│  │  ├─ 500.html
│  │  └─ pdf/
│  │     ├─ invoice_standard.html
│  │     ├─ invoice_modern.html
│  │     └─ invoice_elegant.html
│  └─ static/
│     ├─ css/billipocket.css
│     └─ js/billipocket.js
├─ run.py                    # kohalik käivitus (port 5010)
├─ wsgi.py                   # tootmises WSGI serverile
├─ requirements.txt          # pinnutatud versioonid
├─ README.md                 # lühijuhend
└─ tests/                    # pytest üksus- ja integratsioonitestid
   ├─ unit/
   ├─ integration/
   └─ conftest.py
```

**Mustrid ja põhimõtted:**
- **App Factory**: `create_app(config_name)` loob rakenduse, et toetada eri seadistusi (dev/prod/test).
- **Blueprintid**: loogiline jaotus (dashboard/clients/invoices/pdf).
- **ORM**: SQLAlchemy, välisvõtmed ja kaskaadid, indeksid.
- **Vormid**: Flask-WTF + CSRF.
- **Teenused**: äriloogika (arvenumber, summad) eraldi `services/` kataloogis.
- **PDF**: WeasyPrint; 3 teemat; **üks A4** (vajadusel skaleerimine/truncate).

---

## 3. Paigaldus ja käivitamine (arendus)

**Eeldused (macOS):**
- Python 3.10+
- Homebrew ja süsteemiraamatukogud WeasyPrintile:
  ```bash
  brew install cairo pango gdk-pixbuf libffi
  ```

**Sammud:**
```bash
cd ~/Downloads/billipocket_gpt5
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py      # skeletoni puhul
# või sihtarhitektuuris:
python run.py
```

**URL:** http://127.0.0.1:5010/

**Märkused:**
- Kui port 5010 on juba kasutusel: muuda `run.py` argumendiks `port=5011` või anna käsureal `--port`.
- Kui WeasyPrint puudub või viskab erroreid, kontrolli, et Cairo/Pango/GDK-Pixbuf/libffi on paigaldatud.

---

## 4. Konfiguratsioon

**config.py (soovitus):**
```python
class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///billipocket.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = 3600

class DevelopmentConfig(BaseConfig):
    DEBUG = True

class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
```

**Keskkonnamuutujad (.env/.flaskenv):**
- `FLASK_APP=run.py`
- `FLASK_ENV=development|production`
- `SECRET_KEY=...`
- `DATABASE_URL=sqlite:///billipocket.db` (või PostgreSQL/MySQL)

---

## 5. Andmemudel

**Tabelid ja suhted:**

- **Client**
  - `id` (PK)
  - `name` *(str, required, unikaalsus: soovituslik)*
  - `registry_code` *(str, optional)*
  - `email` *(str, valid e-mail)*
  - `phone` *(str, optional)*
  - `address` *(str, optional)*
  - `created_at` *(datetime, default now)*
  - **Suhe**: 1–N `Invoice`

- **Invoice**
  - `id` (PK)
  - `number` *(str, unique, formaat `YYYY-####`)*
  - `client_id` *(FK → Client.id, ON DELETE RESTRICT)*
  - `date` *(date, required)*
  - `due_date` *(date, required, >= date)*
  - `subtotal` *(Decimal, >= 0)*
  - `vat_rate` *(Decimal, e.g. 22)*
  - `total` *(Decimal, >= subtotal)*
  - `status` *(enum: draft|sent|paid|overdue)*
  - `created_at`, `updated_at`
  - **Suhe**: 1–N `InvoiceLine` (kaskaad kustutamisel)

- **InvoiceLine**
  - `id` (PK)
  - `invoice_id` *(FK → Invoice.id, ON DELETE CASCADE)*
  - `description` *(str, required)*
  - `qty` *(Decimal, >0)*
  - `unit_price` *(Decimal, >=0)*
  - `line_total` *(Decimal, = qty * unit_price)*

**ASCII ER-diagramm:**
```
Client (1) ────< Invoice (1) ────< InvoiceLine
```

**Indeksid/konstraiendid:**
- `Invoice.number` UNIQUE
- `Invoice.client_id` index
- `Invoice.status` index (kiirem filtreerimine)
- `InvoiceLine.invoice_id` index

---

## 6. Arvenumbrite genereerimine

**Loogika (services/numbering.py):**
- Võta jooksev aasta `YYYY`.
- Leia maksimaalne järjekorranumber samal aastal (nt 0007).
- Suurenda +1 ja vorminda `YYYY-####` (neljakohaline pad).
- Tagasta vaba number; hoia unikaalsust transaktsiooni piires.

**Näide:**
- Olemas: `2025-0001 … 2025-0042` → uus: `2025-0043`.

---

## 7. Summade arvutus ja KM

**Loogika (services/totals.py):**
- `line_total = qty * unit_price` iga rea kohta.
- `subtotal = sum(line_total)`.
- `vat = subtotal * (vat_rate/100)`.
- `total = subtotal + vat`.
- Väljad hoia `Decimal`ina, ümarda sobival hetkel (nt 2 kohta).

---

## 8. Vormid ja valideerimine

**Flask-WTF vormid (forms.py):**
- `ClientForm`: `name` (required), `email` (Email), `phone` (optional), `address` (optional).
- `InvoiceForm`: klient (SelectField), kuupäevad (DateField), KM määr (DecimalField), dünaamilised realiinid (FieldList / wtforms_components või custom).
- Serveripoolsed vead kuvatakse **eesti keeles**.
- HTML5 attribuudid (nt `required`, `min="0"`, `step="0.01"`) kliendipoolseks kontrolliks.

---

## 9. Marsruudid (URL-id)

**Lehed (GET/POST):**
- `/` – Ülevaade (dashboard).
- `/clients` – loend + otsing/filtrid.
- `/clients/new` – uus klient (GET vorm, POST salvestus).
- `/clients/<id>/edit` – kliendi muutmine.
- `/clients/<id>/delete` – kliendi kustutamine (POST, CSRF, confirm).
- `/invoices` – loend, filtreerimine staatuse/kuupäeva/kliendi järgi.
- `/invoices/new` – uue arve vorm, realiinide lisamine/eemaldamine.
- `/invoices/<id>/edit` – muutmine.
- `/invoices/<id>/delete` – kustutamine.
- `/invoices/<id>/status` – staatuse muutus (POST: draft→sent→paid).
- `/invoice/<id>/pdf[?style=modern|elegant]` – PDF renderdus.

**API (valikuline tulevikuks):**
- `/api/clients` (GET/POST), `/api/clients/<id>` (GET/PUT/DELETE)
- `/api/invoices` (GET/POST), `/api/invoices/<id>` (GET/PUT/DELETE)

---

## 10. PDF renderdus (WeasyPrint)

**Mallid:**
- `pdf/invoice_standard.html`
- `pdf/invoice_modern.html`
- `pdf/invoice_elegant.html`

**A4 nõue:** tagada, et väljund **mahuks ühele lehele**. Taktikad:
- Sisu marginaalid + fontide suurus.
- Pikemate kirjelduste **truncate** või **scale** (CSS @page + transform).
- Valikulise sisualade peitmine (nt „Märkused“) PDF-is, kui ruumi napib.

**Endpoint:**
```
GET /invoice/<id>/pdf?style=modern
```

---

## 11. Turvalisus ja logimine

- **CSRF**: kõigil POST-vormidel.
- **Sisendi puhastamine**: wtforms valideerimine, serveripoolsed kontrollid.
- **Peidetud andmed**: keskkonnamuutujates (.env), ära versioonikontrolli.
- **Logimine**:
  - Arenduses: console.
  - Tootmises: faililogimine `logs/app.log`, rotatsioon.

---

## 12. CLI käsud

- `flask init-db` – loob tabelid.
- `flask seed-data` – lisab demoandmed (kliendid, arved, read).
- `flask create-admin` – broneeritud tulevase autentimise jaoks.

**Näide:**
```bash
export FLASK_APP=run.py
flask init-db
flask seed-data
```

---

## 13. Testimine (pytest)

**Strateegia:**
- **Unit**: mudelite loogika (numbering, totals, valideerimine).
- **Integration**: CRUD vood (kliendid, arved).
- **E2E smoke**: loo klient → loo arve rea(de)ga → hangi PDF (status 200).

**Käivitamine:**
```bash
pytest -q
```

**Katvuse raport (soovi korral):**
```bash
pytest --cov=app --cov-report=term-missing
```

---

## 14. Deploy (Apache mod_wsgi või Gunicorn)

### 14.1 Apache (mod_wsgi)
1. Serveris loo venv ja paigalda nõuded.
2. Pane projekt: `/www/apache/domains/www.mainedisain.ee/htdocs/invoicemanager/`.
3. Lisa `wsgi.py`:
   ```python
   from app import create_app
   application = create_app('ProductionConfig')
   ```
4. Apache vhostis:
   ```apache
   WSGIDaemonProcess billipocket python-home=/path/to/venv python-path=/path/to/project
   WSGIScriptAlias / /path/to/project/wsgi.py
   <Directory /path/to/project>
       Require all granted
   </Directory>
   ```
5. SQLite faili- ja kaustaõigused (kirjutusõigus protsessi kasutajale).

### 14.2 Gunicorn + reverse proxy
```bash
gunicorn -w 2 -b 127.0.0.1:5010 wsgi:application
# Nginx/Apache proxy edastab liikluse 5010 -> 443/80
```

---

## 15. Varundus ja migratsioonid

- **SQLite varundus**: kopeeri `.db` fail turvalisse asukohta (peatades protsessi vältimaks lukke).
- **Alembic**: skeemimuudatuste versioonihaldus; lisa eraldi kui mudelid valmivad.

---

## 16. Veaotsing (FAQ)

- **Port 5010 on kasutusel** → käivita `python run.py --port 5011` või muuda koodis port.
- **WeasyPrint error „library not found“** → installi `cairo pango gdk-pixbuf libffi` (macOS: brew).
- **PDF ei mahu A4** → vähenda marginaale, vähenda fonti, rakenda truncation (CSS + Jinja lühendamine).
- **SQLite „permission denied“** → kontrolli failiõiguseid; tee DB failile ja projektikataloogile kirjutusõigus protsessi kasutajale.
- **CSRF token missing** → veendu, et vormimallides on `{ form.csrf_token }` ja appis on seadistatud `SECRET_KEY`.

---

## 17. Stiilijuhis ja UX põhimõtted

- **Esteetika**: tumesinine sidebar (#18476b), türkiissinine aktsent (#11D6DE), hele taust (#e1eff0).
- **Loetavus**: Inter font, piisav kontrast, 12–16px baas, selged labelid eesti keeles.
- **Komponendid**: korduvkasutatavad kaardid, vormiväljade grupid, badge’iga staatused.
- **Juurdepääsetavus**: label’id, aria-atribuudid, klaviatuuriga navigeeritavus.

---

## 18. Roadmap (soovitused)

- Kasutaja autentimine (admin/rolle) + sessioonid.
- Failipõhised logod ja templated emailid (arve saatmine).
- Ekspordid: koond-PDF raportid, CSV/Excel.
- Otsing ES-harnase indekseerimisega (optsioonina).
- i18n: kui vaja, lisada inglise tõlge.

---

## 19. Kuidas kasutada Claude Code agente

- **project-architect**: muuda skeleton sihtarhitektuuriks (app factory + blueprints, config).
- **backend-developer**: SQLAlchemy mudelid, vormid, CRUD, numbering/totals, PDF (3 stiili), CLI käsud.
- **frontend-designer**: viimistletud Jinja templated (eesti keeles), sort/filtrid, dünaamilised realiinid.
- **integration-specialist**: vormide ühendamine route’idega, CSRF, flash, 404/500, staatuse vood.
- **test-engineer**: pytest unit + integration + E2E; katvuse raport.
- **deployment-optimizer**: run.py, wsgi.py, tootmisseadistused, README (EE), logimine.

**Tööjärjekord**: Architect → Backend → Frontend → Integration → Tests → Deployment.

---

## 20. Kiirkäskude spikker

```bash
# venv ja sõltuvused
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# DB algus
export FLASK_APP=run.py
flask init-db
flask seed-data

# Käivitus
python run.py           # default port 5010
python run.py --port 5011

# Testid
pytest -q
pytest --cov=app --cov-report=term-missing
```
