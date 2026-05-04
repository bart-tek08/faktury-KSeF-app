from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import os
from lxml import etree
import pandas as pd
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "energa-ksef-2026-ultra-secure"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Dane do logowania
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

def parse_ksef_xml(xml_path):
    """Odporny na błędy parser XML KSeF Energa."""
    try:
        tree = etree.parse(xml_path)
        
        # Uniwersalna funkcja wyciągająca tekst z tagów bez względu na namespace
        def get_text(tag_name):
            res = tree.xpath(f"//*[local-name()='{tag_name}']")
            return res[0].text if res else ""

        # 1. Dane podstawowe (Faktura i Podmioty)
        data = {
            "numer_faktury": get_text("P_2"),
            "numer_faktury_korygowanej": get_text("P_21"), # Pojawi się tylko w korektach
            "kwota_brutto": get_text("P_15"),
            "sprzedawca_nip": get_text("NIP"), # Pierwszy NIP w pliku to Sprzedawca[cite: 2]
        }

        # 2. Wyciąganie kWh z sekcji DodatkowyOpis[cite: 2, 3]
        kwh_val = ""
        opisy = tree.xpath("//*[local-name()='DodatkowyOpis']")
        for opis in opisy:
            klucz = opis.xpath(".//*[local-name()='Klucz']/text()")
            if klucz and "Ilość kWh łącznie" in klucz[0]:
                wartosc = opis.xpath(".//*[local-name()='Wartosc']/text()")
                kwh_val = wartosc[0].replace(" kWh", "").strip() if wartosc else ""
        data["zuzycie_kWh"] = kwh_val

        # 3. Rozbicie pola P_7 (PPE | Taryfa | DataOd | DataDo)[cite: 2, 3]
        p7_raw = get_text("P_7")
        if "|" in p7_raw:
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
        print(f"Błąd podczas czytania pliku {xml_path}: {e}")
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
        return jsonify({"success": False, "error": "Brak plików"}), 400
    
    files = request.files.getlist('files')
    all_results = []
    
    for f in files:
        if f.filename.endswith('.xml'):
            filename = secure_filename(f.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            f.save(path)
            
            parsed_data = parse_ksef_xml(path)
            if parsed_data:
                parsed_data['nazwa_pliku'] = f.filename
                all_results.append(parsed_data)
            
            os.remove(path) # Czyścimy serwer po przetworzeniu
                
    return jsonify({"success": True, "data": all_results})

@app.route('/download_csv', methods=['POST'])
def download_csv():
    req_data = request.json.get('data')
    if not req_data:
        return jsonify({"error": "Brak danych do pobrania"}), 400
    
    df = pd.DataFrame(req_data)
    
    # Ustalenie kolejności kolumn w raporcie
    cols_order = [
        'nazwa_pliku', 'numer_faktury', 'numer_faktury_korygowanej', 
        'numer_PPE', 'taryfa', 'zuzycie_kWh', 'kwota_brutto', 
        'data_od', 'data_do'
    ]
    
    # Wybieramy tylko te kolumny, które faktycznie istnieją w danych
    final_cols = [c for c in cols_order if c in df.columns]
    df = df[final_cols]
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as tmp:
        df.to_csv(tmp.name, index=False, sep=";")
        path = tmp.name
        
    return send_file(path, as_attachment=True, download_name="raport_ksef_energa.csv")

if __name__ == '__main__':
    # Uruchomienie serwera
    app.run(debug=True, port=5000)