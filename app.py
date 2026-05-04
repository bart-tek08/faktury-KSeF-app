from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import os
from lxml import etree
import pandas as pd
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "energa-ksef-2026-v4"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

def parse_ksef_xml(xml_path):
    try:
        tree = etree.parse(xml_path)
        def get_text(tag_name):
            res = tree.xpath(f"//*[local-name()='{tag_name}']")
            return res[0].text if res else ""

        # Pobieranie NIPów i Nazw (zazwyczaj 0 to Sprzedawca, 1 to Nabywca)
        nipy = tree.xpath("//*[local-name()='NIP']/text()")
        nazwy = tree.xpath("//*[local-name()='Nazwa']/text()")

        parsed = {
            "numer_faktury": get_text("P_2"),
            "sprzedawca": nazwy[0] if len(nazwy) > 0 else "Nie znaleziono",
            "nip_sprzedawca": nipy[0] if len(nipy) > 0 else "",
            "nabywca": nazwy[1] if len(nazwy) > 1 else "Nie znaleziono",
            "nip_nabywca": nipy[1] if len(nipy) > 1 else "",
            "kwota_brutto": get_text("P_15"),
            "zuzycie_kwh": 0,
            "ppe": "",
            "taryfa": "",
            "data_od": "",
            "data_do": ""
        }

        # Wyciąganie kWh z pola DodatkowyOpis
        opisy = tree.xpath("//*[local-name()='DodatkowyOpis']")
        for opis in opisy:
            klucz = opis.xpath(".//*[local-name()='Klucz']/text()")
            if klucz and "Ilość kWh łącznie" in klucz[0]:
                val = opis.xpath(".//*[local-name()='Wartosc']/text()")
                if val:
                    clean_val = val[0].replace(" kWh", "").replace(",", ".").replace(" ", "").strip()
                    parsed["zuzycie_kwh"] = float(clean_val)

        # Dane techniczne (PPE, Taryfa, Daty) z pola P_7
        p7 = get_text("P_7")
        if "|" in p7:
            p = p7.split("|")
            parsed["ppe"] = p[1] if len(p) > 1 else ""
            parsed["taryfa"] = p[2] if len(p) > 2 else ""
            parsed["data_od"] = p[3] if len(p) > 3 else ""
            parsed["data_do"] = p[4] if len(p) > 4 else ""

        return parsed
    except Exception as e:
        print(f"Błąd parsera: {e}")
        return None

@app.route('/')
def index():
    if not session.get('logged_in'): return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USER and request.form['password'] == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files')
    results = []
    total_kwh = 0
    for f in files:
        if f.filename.endswith('.xml'):
            path = os.path.join(UPLOAD_FOLDER, secure_filename(f.filename))
            f.save(path)
            data = parse_ksef_xml(path)
            if data:
                data['filename'] = f.filename
                results.append(data)
            os.remove(path)
    
    # Obliczamy statystyki dla tej konkretnej paczki (JS zajmie się resztą)
    total_batch_kwh = sum(item['zuzycie_kwh'] for item in results)
    
    return jsonify({
        "success": True, 
        "data": results,
        "batch_total": round(total_batch_kwh, 2)
    })

@app.route('/download_csv', methods=['POST'])
def download_csv():
    data = request.json.get('data')
    df = pd.DataFrame(data)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as tmp:
        df.to_csv(tmp.name, index=False, sep=";")
        return send_file(tmp.name, as_attachment=True, download_name="raport_ksef.csv")

if __name__ == '__main__':
    app.run(debug=True)