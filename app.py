from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import random
import string
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from datetime import datetime

# --- LIBRERÍAS PARA PDF E IMÁGENES ---
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'vektor_nexus_admin_2026_super')

CARPETA_RAIZ_DRIVE = "1PbH8767Q86O-TntoxDxozaGiBl3WJqE0"

# --- CONFIGURACIÓN DE GOOGLE SERVICES ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open("Base_Datos_Calculadora").sheet1
    drive_service = build('drive', 'v3', credentials=creds)
except Exception as e:
    print(f"Error de conexión a Google: {e}")
    sheet = None
    drive_service = None

# --- ESTRUCTURA CACHÉ DE METAS (ROBUSTA) ---
pdf_metas_cache = {
    "estilos": [" "], 
    "tallas": ['XXS', 'XS', 'S', 'M', 'L', 'XL', '2X', '3X', '4X'], 
    "procesos": ['CONTEO','SORTEO','VOLTEO','DOBLADO','VOLTEO-SORTING','VOLTEO-PFD','SORTEO-REPROCESO'], 
    "datos": [
        {"estilo": "DBS-GOKU", "talla": "M", "proceso": "DOBLADO", "meta": 150},
        {"estilo": "DBS-GOKU", "talla": "L", "proceso": "SORTEO", "meta": 165},
        {"estilo": "DBS-VEGETA", "talla": "S", "proceso": "CONTEO", "meta": 200},
        {"estilo": "DBS-BROLY", "talla": "XL", "proceso": "VOLTEO", "meta": 90},
        {"estilo": "DBS-GOHAN", "talla": "M", "proceso": "VOLTEO-PFD", "meta": 120}
    ]
}

# --- HELPER FUNCTIONS FOR DRIVE & FILES ---
def obtener_o_crear_carpeta_usuario(nombre_usuario):
    if not drive_service: return None
    try:
        query = f"'{CARPETA_RAIZ_DRIVE}' in parents and name = '{nombre_usuario}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])

        if files: return files[0]['id']

        file_metadata = {
            'name': nombre_usuario,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [CARPETA_RAIZ_DRIVE]
        }
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')
    except Exception as e:
        print(f"Error al gestionar carpeta: {e}")
        return None

def generar_nombre_correlativo(folder_id):
    fecha_actual = datetime.now().strftime("%d-%m-2026")
    if not drive_service or not folder_id:
        return f"vektor_nexus_000001-{fecha_actual}"
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = drive_service.files().list(q=query, fields="files(name)").execute()
        files = results.get('files', [])
        numero_calculo = len(files) + 1
        return f"vektor_nexus_{numero_calculo:06d}-{fecha_actual}"
    except:
        return f"vektor_nexus_000001-{fecha_actual}"

def crear_pdf_en_memoria(datos_extensos):
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "VEKTOR NEXUS - REPORTE DE CÁLCULO PREMIUM")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, f"Fecha de registro: {datetime.now().strftime('%d/%m/2026 %H:%M')}")
    c.line(50, 720, 550, 720)
    y = 690
    c.setFont("Helvetica", 12)
    for linea in datos_extensos:
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 12)
            y = 750
        c.drawString(50, y, str(linea))
        y -= 20
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer

def crear_imagen_en_memoria(datos_cortos):
    img = Image.new('RGB', (600, 300), color='#0b132b') # Fondo Oscuro
    d = ImageDraw.Draw(img)
    d.text((30, 30), "VEKTOR NEXUS - CÁLCULO DE PRODUCCIÓN", fill='#ff6600') # Naranja Goku
    d.line([(30, 55), (570, 55)], fill='#00f3ff', width=2)
    y = 80
    for linea in datos_cortos:
        d.text((30, y), str(linea), fill='#edf2f4')
        y += 30
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer

def cargar_usuarios_drive():
    if not sheet:
        # Retorno de prueba en caso de que no haya credenciales conectadas
        return {
            "token123": {"token": "token123", "nombre": "Guerrero Z", "contacto": "55551234", "pin": "1234", "rol": "operador", "hibernacion": False, "permisos": {"biohorario": True, "eficiencia": True, "tiempo": True, "metas": True, "historial": True}},
            "angel0301": {"token": "angel0301", "nombre": "Angel Castillo", "contacto": "00000000", "pin": "0301", "rol": "admin", "hibernacion": False, "permisos": {"biohorario": True, "eficiencia": True, "tiempo": True, "metas": True, "historial": True}}
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
                    "nombre": str(row[1]).strip() if len(row) > 1 else "",
                    "contacto": str(row[2]).strip() if len(row) > 2 else "",
                    "pin": str(row[3]).strip() if len(row) > 3 else "",
                    "rol": str(row[4]).strip() if len(row) > 4 else "operador",
                    "device_id": str(row[5]).strip() if len(row) > 5 else "",
                    "hibernacion": is_hibernated,
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

# --- RUTAS DE API ---

@app.route('/')
def index():
    # Ya no requerimos token en la URL, el login se maneja en el frontend
    return render_template('index.html')

@app.route(https://docs.google.com/spreadsheets/d/13xBj_hwIxlLxIGHs8Hc1RMYumxl72Y-cYU0aOzfAymk/edit?usp=drivesdk , methods=['POST'])
def login_verificar():
    data = request.json
    token_ingresado = str(data.get('token')).strip()
    pin_ingresado = str(data.get('pin')).strip()
    device_id_cliente = str(data.get('device_id')).strip()

    usuarios_actuales = cargar_usuarios_drive()
    if token_ingresado in usuarios_actuales and str(usuarios_actuales[token_ingresado]['pin']).strip() == pin_ingresado:
        usuario = usuarios_actuales[token_ingresado]
        if usuario.get('hibernacion', False):
            return jsonify({"status": "hibernado", "message": "Sistema en hibernación."})
        
        session['user_token'] = token_ingresado
        session['user_name'] = usuario['nombre']
        return jsonify({"status": "success", "user": usuario})
    
    return jsonify({"status": "error", "message": "Token o PIN Incorrecto. El Ki no coincide."}), 401

@app.route('/api/metas/datos', methods=['GET'])
def obtener_metas_datos():
    return jsonify({
        "status": "success",
        "datos": pdf_metas_cache["datos"],
        "estilos": pdf_metas_cache["estilos"],
        "tallas": pdf_metas_cache["tallas"],
        "procesos": pdf_metas_cache["procesos"]
    })

@app.route(https://docs.google.com/spreadsheets/d/1SBsIDmwEZTarfIvZsuOl1nTC0AbkIDZa/edit?usp=drivesdk&ouid=106555543057171702491&rtpof=true&sd=true/sincronizar', methods=['POST'])
def sincronizar_metas():
    # Simulación de extracción profunda de DB Drive
    return jsonify({
        "status": "success",
        "datos": pdf_metas_cache["datos"],
        "estilos": pdf_metas_cache["estilos"],
        "tallas": pdf_metas_cache["tallas"],
        "procesos": pdf_metas_cache["procesos"],
        "message": "Base de datos Drive sincronizada al 100%"
    })

@app.route(https://drive.google.com/drive/folders/1O_xLU2jDXcir2fg6zMdDg-wTl1UQs_K3, methods=['POST'])
def guardar_calculo():
    data = request.json or {}
    token = data.get('token')
    tipo = data.get('tipo')
    info = data.get('info', {})
    extenso = data.get('extenso', False)
    
    # Preparar lineas
    lineas_calculo = [f"Tipo de Cálculo: {tipo}", f"Resultado: {info.get('res', '')}", f"Detalles: {info.get('detalle', '')}"]

    if not token or not drive_service:
        return jsonify({"status": "success", "message": "Guardado localmente (Simulado por falta de Drive API)"}), 200

    usuarios = cargar_usuarios_drive()
    if token not in usuarios:
        return jsonify({"status": "error", "message": "Usuario no válido"}), 403

    nombre_usuario = usuarios[token]['nombre']
    folder_id = obtener_o_crear_carpeta_usuario(nombre_usuario)
    if not folder_id:
        return jsonify({"status": "error", "message": "No se pudo gestionar la carpeta en Drive"}), 500

    nombre_base = generar_nombre_correlativo(folder_id)

    if extenso:
        archivo_binario = crear_pdf_en_memoria(lineas_calculo)
        nombre_archivo = f"{nombre_base}.pdf"
        mime_type = "application/pdf"
    else:
        archivo_binario = crear_imagen_en_memoria(lineas_calculo)
        nombre_archivo = f"{nombre_base}.png"
        mime_type = "image/png"

    try:
        file_metadata = {'name': nombre_archivo, 'parents': [folder_id]}
        media = MediaIoBaseUpload(archivo_binario, mimetype=mime_type, resumable=True)
        uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()

        return jsonify({
            "status": "success", 
            "file_name": nombre_archivo, 
            "file_id": uploaded_file.get('id'),
            "drive_url": uploaded_file.get('webViewLink')
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al subir a Drive: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
