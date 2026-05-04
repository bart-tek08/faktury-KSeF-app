from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import os
from lxml import etree
import pandas as pd
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "ksef-energa-sekret"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Dane do logowania
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

def parse_ksef_xml(xml_path):
    """Wyciąga specyficzne dane Energa z XML KSeF FA(3)."""
    try:
        tree = etree.parse(xml_path)
        root = tree.getroot()
        ns = root.nsmap

        # Funkcja pomocnicza do szukania tagów z namespace ns2 lub bez
        def find_val(xpath):
            res = tree.xpath(xpath, namespaces=ns)
            return res[0].text if res else ""

        # 1. Dane podstawowe i Podmioty
        data = {
            "numer_faktury": find_val(".//ns2:P_2 | .//P_2"),
            "kwota_brutto": find_val(".//ns2:P_15 | .//P_15"),
            "sprzedawca_nazwa": find_val(".//ns2:Podmiot1//ns2:Nazwa | .//Podmiot1//Nazwa"),
            "sprzedawca_nip": find_val(".//ns2:Podmiot1//ns2:NIP | .//Podmiot1//NIP"),
            "nabywca_nazwa": find_val(".//ns2:Podmiot2//ns2:Nazwa | .//Podmiot2//Nazwa"),
            "nabywca_nip": find_val(".//ns2:Podmiot2//ns2:NIP | .//Podmiot2//NIP"),
        }

        # 2. Ilość kWh z DodatkowyOpis
        kwh_val = ""
        opisy = tree.xpath(".//ns2:DodatkowyOpis | .//DodatkowyOpis", namespaces=ns)
        for opis in opisy:
            klucz = opis.xpath("./ns2:Klucz/text() | ./Klucz/text()", namespaces=ns)
            if klucz and "Ilość kWh łącznie" in klucz[0]:
                val = opis.xpath("./ns2:Wartosc/text() | ./Wartosc/text()", namespaces=ns)
                kwh_val = val[0].replace(" kWh", "") if val else ""
        data["zuzycie_kWh"] = kwh_val

        # 3. Rozbicie pola P_7 (PPE, Taryfa, Daty)
        # Format: Tekst|PPE|Taryfa|DataOd|DataDo
        p7_raw = find_val(".//ns2:FaWiersz/ns2:P_7 | .//FaWiersz/P_7")
        
        if p7_raw and "|" in p7_raw:
            parts = p7_raw.split("|")
            data["numer_PPE"] = parts[1] if len(parts) > 1 else ""
            data["taryfa"] = parts[2] if len(parts) > 2 else ""
            data["data_od"] = parts[3] if len(parts) > 3 else ""
            data["data_do"] = parts[4] if len(parts) > 4 else ""
        else:
            data["numer_PPE"] = ""
            data["taryfa"] = ""
            data["data_od"] = ""
            data["data_do"] = ""

        return data
    except Exception as e:
        print(f"Błąd podczas parsowania {xml_path}: {e}")
        return None

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
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
    if 'files' not in request.files:
        return jsonify({"error": "Brak plików"}), 400
    
    files = request.files.getlist('files')
    all_data = []
    
    for f in files:
        if f.filename.endswith('.xml'):
            filename = secure_filename(f.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            f.save(path)
            
            parsed = parse_ksef_xml(path)
            if parsed:
                parsed['nazwa_pliku'] = f.filename
                all_data.append(parsed)
            
            os.remove(path)
                
    return jsonify({"success": True, "data": all_data})

@app.route('/download_csv', methods=['POST'])
def download_csv():
    data = request.json.get('data')
    df = pd.DataFrame(data)
    # Zmiana kolejności kolumn na bardziej czytelną
    cols = ['nazwa_pliku', 'numer_faktury', 'nabywca_nazwa', 'numer_PPE', 'taryfa', 'zuzycie_kWh', 'kwota_brutto', 'data_od', 'data_do']
    df = df[cols]
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as tmp:
        df.to_csv(tmp.name, index=False, sep=";")
        path = tmp.name
    return send_file(path, as_attachment=True, download_name="raport_energa_ksef.csv")

if __name__ == '__main__':
    app.run(debug=True, port=5000)