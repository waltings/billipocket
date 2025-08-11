# Billipocket (Flask)
**Port:** 5010

Kiirstart:
1. Loo virtuaalkeskkond ja paigalda:
   ```
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **macOS**: vajad Cairo, Pango, GDK-Pixbuf, libffi
   ```
   brew install cairo pango gdk-pixbuf libffi
   ```
3. Käivita:
   ```
   python app.py
   ```
4. Ava brauseris http://127.0.0.1:5010/

PDF-nupp lehel **Arved** kasutab WeasyPrinti ja malli `templates/invoice_pdf.html`.
