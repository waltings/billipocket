from flask import Flask, render_template, request, send_file, url_for
from datetime import date
from io import BytesIO
from weasyprint import HTML

app = Flask(__name__)

# --- Demo-andmed (asenda hiljem DB-ga) ---
CLIENTS = [
    {"name":"Nordics OÜ","invoices":7,"last":"2025-08-10"},
    {"name":"Viridian AS","invoices":3,"last":"2025-08-08"},
]
INVOICES = [
    {"no":"#2025-0042","date":"2025-08-10","client":"Nordics OÜ","total":420.00,"status":"unpaid"},
    {"no":"#2025-0041","date":"2025-08-08","client":"Viridian AS","total":1280.00,"status":"paid"},
]

@app.context_processor
def inject_nav():
    return {"nav": {
        "overview": url_for('overview'),
        "invoices": url_for('invoices'),
        "clients": url_for('clients'),
        "reports": url_for('reports'),
        "settings": url_for('settings'),
    }}

@app.route('/')
def overview():
    metrics = {
        "revenue_month": 12480,
        "cash_in": 9210,
        "unpaid": sum(1 for i in INVOICES if i['status']!="paid"),
        "avg_days": 13,
    }
    return render_template('overview.html', metrics=metrics)

@app.route('/invoices')
def invoices():
    status = request.args.get('status')
    items = INVOICES
    if status in {"paid","unpaid","overdue"}:
        items = [i for i in INVOICES if i['status']==status]
    return render_template('invoices.html', invoices=items, status=status)

@app.route('/clients')
def clients():
    return render_template('clients.html', clients=CLIENTS)

@app.route('/reports')
def reports():
    return render_template('reports.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

# --- PDF genereerimine (arve) ---
@app.route('/invoice/<inv_no>/pdf')
def invoice_pdf(inv_no):
    inv = next((i for i in INVOICES if i['no']==inv_no), None)
    if not inv:
        return "Arvet ei leitud", 404
    html = render_template('invoice_pdf.html', inv=inv, today=date.today())
    pdf = HTML(string=html, base_url=request.base_url).write_pdf()
    return send_file(BytesIO(pdf), mimetype='application/pdf', download_name=f"{inv_no}.pdf")

if __name__ == '__main__':
    app.run(debug=True, port=5010)
