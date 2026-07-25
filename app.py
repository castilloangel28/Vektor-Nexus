import os
import io
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'vektor_nexus_secret_key_2026')

# --- CONFIGURACIÓN DE IDs DE GOOGLE SHEETS Y DRIVE ---
SPREADSHEET_USUARIOS_ID = '1flxIGd4eBiGYe2vrSsPU318Feg2KHFV4Ip9oTF2aPvA'
SPREADSHEET_METAS_ID = '13xBj_hwIxlLxIGHs8Hc1RMYumxl72Y-cYU0aOzfAymk'
CARPETA_RAIZ_DRIVE = '1PbH8767Q86O-TntoxDxozaGiBl3WJqE0'

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

creds = None
client_gspread = None
sheet_usuarios = None
sheet_metas = None
drive_service = None

def inicializar_servicios_google():
    global creds, client_gspread, sheet_usuarios, sheet_metas, drive_service
    try:
        if os.path.exists('credenciales.json'):
            creds = Credentials.from_service_account_file('credenciales.json', scopes=SCOPES)
        else:
            json_creds = os.environ.get('GOOGLE_CREDENTIALS_JSON')
            if json_creds:
                creds = Credentials.from_service_account_info(json.loads(json_creds), scopes=SCOPES)

        if creds:
            client_gspread = gspread.authorize(creds)
            sheet_usuarios = client_gspread.open_by_key(SPREADSHEET_USUARIOS_ID).sheet1
            
            doc_metas = client_gspread.open_by_key(SPREADSHEET_METAS_ID)
            try:
                sheet_metas = doc_metas.worksheet("Datos PDF")
            except Exception:
                sheet_metas = doc_metas.sheet1
                
            drive_service = build('drive', 'v3', credentials=creds)
            print(" Conexión a Google Sheets y Drive establecida.")
    except Exception as e:
        print(f" Error inicializando servicios de Google: {e}")

inicializar_servicios_google()

def obtener_o_crear_carpeta_usuario(nombre_usuario):
    if not drive_service:
        return None
    try:
        query = f"'{CARPETA_RAIZ_DRIVE}' in parents and name = '{nombre_usuario}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])

        if files:
            return files[0]['id']

        file_metadata = {
            'name': nombre_usuario,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [CARPETA_RAIZ_DRIVE]
        }
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')
    except Exception as e:
        print(f"Error en carpetas de Drive: {e}")
        return None

def cargar_usuarios_db():
    if not sheet_usuarios:
        return {}
    try:
        rows = sheet_usuarios.get_all_values()
        usuarios = {}
        for r in rows[1:]:
            if len(r) > 0 and r[0].strip():
                tkn = r[0].strip()
                hibernado_val = str(r[6]).strip().upper() if len(r) > 6 else 'FALSE'
                is_hibernated = (hibernado_val == 'TRUE')
                
                usuarios[tkn] = {
                    "token": tkn,
                    "nombre": r[1].strip() if len(r) > 1 else "Usuario",
                    "contacto": r[2].strip() if len(r) > 2 else "",
                    "pin": r[3].strip() if len(r) > 3 else "",
                    "rol": r[4].strip() if len(r) > 4 else "operador",
                    "device_id": r[5].strip() if len(r) > 5 else "",
                    "hibernacion": is_hibernated,
                    "ultima_conexion": r[7].strip() if len(r) > 7 else ""
                }
        return usuarios
    except Exception as e:
        print(f"Error al leer usuarios: {e}")
        return {}

def cargar_metas_db():
    if not sheet_metas:
        return {"datos": [], "estilos": [], "tallas": [], "procesos": []}
    try:
        rows = sheet_metas.get_all_values()
        datos = []
        estilos_set = set()
        tallas_set = set()
        procesos_set = set()

        for r in rows[1:]:
            if len(r) >= 6 and r[0].strip():
                estilo = r[0].strip()
                talla = r[1].strip()
                garment = r[2].strip() if len(r) > 2 else ""
                operacion = r[3].strip()
                abrev = r[4].strip() if len(r) > 4 else ""
                
                try:
                    meta_dz_turno = float(r[5].strip()) if len(r) > 5 and r[5].strip() else 0
                    meta_dz_hora = float(r[6].strip()) if len(r) > 6 and r[6].strip() else 0
                    meta_pz_min = float(r[7].strip()) if len(r) > 7 and r[7].strip() else 0
                    meta_pza_hora = round(meta_dz_hora * 12)
                except ValueError:
                    meta_dz_turno = meta_dz_hora = meta_pz_min = meta_pza_hora = 0

                if meta_pza_hora > 0 or meta_dz_turno > 0:
                    datos.append({
                        "estilo": estilo,
                        "talla": talla,
                        "garment": garment,
                        "proceso": operacion,
                        "abrev": abrev,
                        "meta_turno": meta_dz_turno,
                        "meta_dz_hora": meta_dz_hora,
                        "meta_pz_min": meta_pz_min,
                        "meta": meta_pza_hora
                    })
                    estilos_set.add(estilo)
                    tallas_set.add(talla)
                    procesos_set.add(operacion)

        return {
            "datos": datos,
            "estilos": sorted(list(estilos_set)),
            "tallas": sorted(list(tallas_set)),
            "procesos": sorted(list(procesos_set))
        }
    except Exception as e:
        print(f"Error al cargar base de metas: {e}")
        return {"datos": [], "estilos": [], "tallas": [], "procesos": []}

# --- RUTAS DE API Y RENDER ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    token_in = str(data.get('token', '')).strip()
    pin_in = str(data.get('pin', '')).strip()
    device_id_in = str(data.get('device_id', '')).strip()

    usuarios = cargar_usuarios_db()

    if token_in in usuarios:
        usr = usuarios[token_in]
        if usr['pin'] == pin_in:
            if usr['hibernacion']:
                return jsonify({"status": "hibernado", "message": "Tu cuenta ha sido hibernada por el administrador."}), 403
            
            try:
                if sheet_usuarios:
                    cell = sheet_usuarios.find(token_in)
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet_usuarios.update_cell(cell.row, 8, now_str)
                    if device_id_in and not usr['device_id']:
                        sheet_usuarios.update_cell(cell.row, 6, device_id_in)
            except Exception as e:
                print(f"Error actualizando conexión: {e}")

            session['user_token'] = token_in
            return jsonify({"status": "success", "user": usr})
            
    return jsonify({"status": "error", "message": "Credenciales inválidas. Token o PIN incorrecto."}), 401

@app.route('/api/metas/datos', methods=['GET'])
def api_metas_datos():
    res = cargar_metas_db()
    return jsonify({"status": "success", **res})

@app.route('/api/guardar_calculo', methods=['POST'])
def guardar_calculo():
    data = request.get_json() or {}
    token = data.get('token')
    tipo = data.get('tipo', 'CALCULO_GENERAL')
    info = data.get('info', {})
    
    if not token or not drive_service:
        return jsonify({"status": "success", "message": "Procesado localmente."})

    usuarios = cargar_usuarios_db()
    if token not in usuarios:
        return jsonify({"status": "error", "message": "No autorizado"}), 403

    nombre_usuario = usuarios[token]['nombre']
    folder_id = obtener_o_crear_carpeta_usuario(nombre_usuario)

    if folder_id:
        try:
            img_buffer = io.BytesIO()
            img = Image.new('RGB', (700, 450), color='#030712')
            d = ImageDraw.Draw(img)
            
            d.rectangle([10, 10, 690, 440], outline='#ff6600', width=3)
            d.text((30, 30), f"VEKTOR NEXUS - REPORTE DE PRODUCCIÓN", fill='#ff6600')
            d.text((30, 60), f"Tipo: {tipo}", fill='#00f3ff')
            d.text((30, 90), f"Operador: {nombre_usuario} ({token})", fill='#ffffff')
            d.text((30, 115), f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fill='#9ca3af')
            
            y = 160
            for k, v in info.items():
                d.text((30, y), f"{k.upper()}: {v}", fill='#39ff14')
                y += 28

            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)

            file_metadata = {
                'name': f"{tipo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                'parents': [folder_id]
            }
            media = MediaIoBaseUpload(img_buffer, mimetype='image/png', resumable=True)
            drive_service.files().create(body=file_metadata, media_body=media).execute()
        except Exception as e:
            print(f"Error generando reporte de imagen: {e}")

    return jsonify({"status": "success", "message": "Reporte sincronizado en Google Drive"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
