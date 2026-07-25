from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import random
import string
import io
import openpyxl  # Para lectura opcional de Excel (.xlsx)
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from datetime import datetime

# --- LIBRERÍAS PARA PDF E IMÁGENES ---
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'angel_admin_2026_secure')

CARPETA_RAIZ_DRIVE = "1PbH8767Q86O-TntoxDxozaGiBl3WJqE0"

# --- CONFIGURACIÓN DE GOOGLE SERVICES ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = None
sheet = None
drive_service = None

try:
    if os.path.exists('credenciales.json'):
        creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
        client = gspread.authorize(creds)
        sheet = client.open("Base_Datos_Calculadora").sheet1
        drive_service = build('drive', 'v3', credentials=creds)
except Exception as e:
    print(f"⚠️ Error al inicializar conexion con Google Services: {e}")

# --- CACHÉ DE METAS ESTÁNDAR ---
pdf_metas_cache = {
    "estilos": ["ESTILO-A", "ESTILO-B", "ESTILO-C"], 
    "tallas": ['XXS', 'XS', 'S', 'M', 'L', 'XL', '2X', '3X', '4X'], 
    "procesos": ['CONTEO','SORTEO','VOLTEO','DOBLADO','VOLTEO-SORTING','VOLTEO-PFD','SORTEO-REPROCESO'], 
    "datos": [
        {"estilo": "ESTILO-A", "talla": "M", "proceso": "DOBLADO", "meta": 50},
        {"estilo": "ESTILO-B", "talla": "L", "proceso": "SORTEO", "meta": 65}
    ]
}

# --- FUNCIONES AUXILIARES DE DRIVE ---

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
        print(f"Error gestionando carpeta Drive para {nombre_usuario}: {e}")
        return None

def generar_nombre_correlativo(folder_id):
    fecha_actual = datetime.now().strftime("%d-%m-2026")
    if not drive_service or not folder_id:
        return f"calculo000001-{fecha_actual}"
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = drive_service.files().list(q=query, fields="files(name)").execute()
        files = results.get('files', [])

        numero_calculo = len(files) + 1
        str_numero = f"{numero_calculo:06d}"
        return f"calculo{str_numero}-{fecha_actual}"
    except Exception:
        return f"calculo000001-{fecha_actual}"

def crear_pdf_en_memoria(tipo, info):
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, f"REPORTE DE CÁLCULO DE PRODUCCIÓN - {tipo.upper()}")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, f"Fecha de emisión: {datetime.now().strftime('%d/%m/2026 %H:%M:%S')}")
    c.line(50, 720, 550, 720)

    y = 690
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Resultado General: {info.get('res', 'N/A')}")
    y -= 25

    c.setFont("Helvetica", 10)
    detalle = info.get('detalle', '')
    for linea in detalle.split(' | '):
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = 750
        c.drawString(50, y, str(linea))
        y -= 18

    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer

def crear_imagen_en_memoria(tipo, info):
    img = Image.new('RGB', (600, 320), color='#050814')
    d = ImageDraw.Draw(img)

    d.text((30, 30), f"S.I.C.E.P. - RESUMEN ({tipo.upper()})", fill='#00f3ff')
    d.line([(30, 55), (570, 55)], fill='#39ff14', width=2)

    d.text((30, 75), f"Resultado: {info.get('res', 'N/A')}", fill='#ffe600')
    
    y = 120
    detalle = info.get('detalle', '')
    for linea in detalle.split(' | ')[:5]:
        d.text((30, y), str(linea)[:65], fill='#edf2f4')
        y += 25

    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer

def cargar_usuarios_drive():
    if not sheet:
        # Fallback usuarios estáticos en caso de falta de credenciales
        return {
            "angel0301": {
                "token": "angel0301", "nombre": "Angel Castillo", "contacto": "99999999", 
                "pin": "1234", "rol": "admin", "hibernado": False,
                "permisos": {"biohorario": True, "eficiencia": True, "tiempo": True, "metas": True, "historial": True}
            }
        }
    try:
        records = sheet.get_all_values()
        usuarios = {}
        for row in records[1:]:
            if len(row) > 0 and str(row[0]).strip():
                tkn = str(row[0]).strip()
                is_hibernated = str(row[6]).lower() == 'false' if len(row) > 6 and row[6] != "" else False

                usuarios[tkn] = {
                    "token": tkn,
                    "nombre": str(row[1]).strip() if len(row) > 1 else "Operador",
                    "contacto": str(row[2]).strip() if len(row) > 2 else "",
                    "pin": str(row[3]).strip() if len(row) > 3 else "0000",
                    "rol": str(row[4]).strip() if len(row) > 4 else "operador",
                    "device_id": str(row[5]).strip() if len(row) > 5 else "",
                    "hibernado": is_hibernated,
                    "ultima_conexion": str(row[11]).strip() if len(row) > 11 else "Desconocida",
                    "permisos": {
                        "biohorario": not is_hibernated, 
                        "eficiencia": str(row[7]).lower() == 'true' if len(row) > 7 and row[7] != "" else True,
                        "tiempo": str(row[8]).lower() == 'true' if len(row) > 8 and row[8] != "" else True,
                        "metas": str(row[9]).lower() == 'true' if len(row) > 9 and row[9] != "" else True,
                        "historial": str(row[10]).lower() == 'true' if len(row) > 10 and row[10] != "" else True
                    }
                }
        return usuarios
    except Exception as e:
        print("Error al cargar usuarios de Drive:", e)
        return {}

# --- RUTAS Y ENDPOINTS HTTP / REST API ---

@app.route('/')
def index():
    token = request.args.get('token', 'angel0301')
    usuarios_actuales = cargar_usuarios_drive()
    user = usuarios_actuales.get(token, {
        "nombre": "Invitado", "pin": "0000", "rol": "operador",
        "permisos": {"biohorario": True, "eficiencia": True, "tiempo": True, "metas": True, "historial": True}
    })
    return render_template('index.html', user=user, token=token)

@app.route('/api/login', methods=['POST'])
def login_verificar():
    data = request.json or {}
    token = data.get('token')
    pin_ingresado = str(data.get('pin', '')).strip()

    usuarios_actuales = cargar_usuarios_drive()
    if token in usuarios_actuales:
        usr = usuarios_actuales[token]
        if usr['hibernado']:
            return jsonify({"status": "error", "hibernacion": True, "message": "Sistema en Hibernación."}), 403
        if str(usr['pin']).strip() == pin_ingresado:
            session['user_token'] = token
            session['user_name'] = usr['nombre']
            return jsonify({"status": "success", "permisos": usr['permisos'], "hibernacion": False})
    
    return jsonify({"status": "error", "message": "PIN o Token Inválido"}), 401

@app.route('/api/metas/datos', methods=['GET'])
def obtener_metas_datos():
    return jsonify({
        "status": "success",
        "datos": pdf_metas_cache["datos"],
        "estilos": pdf_metas_cache["estilos"],
        "tallas": pdf_metas_cache["tallas"],
        "procesos": pdf_metas_cache["procesos"]
    })

@app.route('/api/metas/sincronizar', methods=['POST'])
def sincronizar_metas():
    return jsonify({
        "status": "success",
        "datos": pdf_metas_cache["datos"],
        "estilos": pdf_metas_cache["estilos"],
        "tallas": pdf_metas_cache["tallas"],
        "procesos": pdf_metas_cache["procesos"]
    })

@app.route('/api/save', methods=['POST'])
@app.route('/api/historial/guardar', methods=['POST'])
def guardar_calculo():
    data = request.json or {}
    token = data.get('token')
    tipo = data.get('tipo', 'General')
    info = data.get('info', {})
    extenso = data.get('extenso', False)

    if not token:
        return jsonify({"status": "error", "message": "Falta token de identificación"}), 400

    usuarios = cargar_usuarios_drive()
    nombre_usuario = usuarios[token]['nombre'] if token in usuarios else "Operador"

    folder_id = obtener_o_crear_carpeta_usuario(nombre_usuario)
    nombre_base = generar_nombre_correlativo(folder_id)

    if extenso:
        archivo_binario = crear_pdf_en_memoria(tipo, info)
        nombre_archivo = f"{nombre_base}.pdf"
        mime_type = "application/pdf"
    else:
        archivo_binario = crear_imagen_en_memoria(tipo, info)
        nombre_archivo = f"{nombre_base}.png"
        mime_type = "image/png"

    drive_url = "#"
    file_id = "local_dummy_id"

    if drive_service and folder_id:
        try:
            file_metadata = {'name': nombre_archivo, 'parents': [folder_id]}
            media = MediaIoBaseUpload(archivo_binario, mimetype=mime_type, resumable=True)
            uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
            file_id = uploaded.get('id')
            drive_url = uploaded.get('webViewLink')
        except Exception as e:
            print(f"Error subiendo a Drive: {e}")

    return jsonify({
        "status": "success", 
        "file_name": nombre_archivo, 
        "file_id": file_id,
        "drive_url": drive_url
    })

@app.route('/api/load', methods=['GET'])
@app.route('/api/historial/archivos', methods=['GET'])
def listar_historial_usuario():
    token = request.args.get('token')
    if not token:
        return jsonify([]), 400

    usuarios = cargar_usuarios_drive()
    if token not in usuarios:
        return jsonify([]), 403

    nombre_usuario = usuarios[token]['nombre']
    folder_id = obtener_o_crear_carpeta_usuario(nombre_usuario)

    if not drive_service or not folder_id:
        return jsonify([])

    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id, name, webViewLink, mimeType, createdTime)").execute()
        files = results.get('files', [])

        formateados = []
        for f in files:
            formateados.append({
                "tipo": f.get('name', 'Reporte').split('-')[0].upper(),
                "fecha_hora": f.get('createdTime', datetime.now().strftime("%d/%m/%Y")),
                "drive_url": f.get('webViewLink'),
                "usuario": nombre_usuario,
                "info": {"res": f.get('name'), "detalle": f.get('mimeType')}
            })
        return jsonify(formateados)
    except Exception as e:
        print("Error al listar historial:", e)
        return jsonify([])

@app.route('/api/admin/usuarios', methods=['GET', 'POST', 'PUT'])
def admin_drive():
    if request.method == 'GET':
        return jsonify(cargar_usuarios_drive())

    data = request.json or {}
    if request.method == 'POST':
        nuevo_token = "tkn_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        nuevo_pin = "".join(random.choices(string.digits, k=4))
        if sheet:
            try:
                sheet.append_row([nuevo_token, data.get('nombre'), data.get('contacto'), nuevo_pin, "operador", "", "true", "true", "true", "true", "true", ""])
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        return jsonify({"status": "success", "token": nuevo_token, "pin": nuevo_pin})

    if request.method == 'PUT':
        token = data.get('token')
        if sheet and token:
            try:
                celda = sheet.find(token)
                if data.get('nombre'): sheet.update_cell(celda.row, 2, data.get('nombre'))
                if data.get('contacto'): sheet.update_cell(celda.row, 3, data.get('contacto'))
                if data.get('nuevo_pin'): sheet.update_cell(celda.row, 4, data.get('nuevo_pin'))
                return jsonify({"status": "success"})
            except Exception:
                return jsonify({"status": "error", "message": "Usuario no encontrado"}), 404
        return jsonify({"status": "success"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
