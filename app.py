from flask import Flask, render_template, request, jsonify, session
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import random
import string
import io
import openpyxl
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'vektor_nexus_key_2026')

CARPETA_RAIZ_DRIVE = "1PbH8767Q86O-TntoxDxozaGiBl3WJqE0"

# CONFIGURACIÓN GOOGLE SERVICES
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open("Base_Datos_Calculadora").sheet1
    drive_service = build('drive', 'v3', credentials=creds)
except Exception as e:
    print(f"Error de conexión a Google Services: {e}")

# CACHE DE METAS DE PRODUCCIÓN
pdf_metas_cache = {
    "estilos": ["ESTILO-A", "ESTILO-B", "ESTILO-C"],
    "tallas": ['XXS', 'XS', 'S', 'M', 'L', 'XL', '2X', '3X', '4X'],
    "procesos": ['CONTEO','SORTEO','VOLTEO','DOBLADO','VOLTEO-SORTING','VOLTEO-PFD','SORTEO-REPROCESO'],
    "datos": [
        {"estilo": "ESTILO-A", "talla": "M", "proceso": "DOBLADO", "meta": 50},
        {"estilo": "ESTILO-B", "talla": "L", "proceso": "SORTEO", "meta": 65}
    ]
}

# COMUNICADOS VIP ADMINISTRADOR EN MEMORIA
comunicados_vip = [
    {
        "id": 1,
        "titulo": "¡BIENVENIDO A VEKTOR NEXUS!",
        "mensaje": "Plataforma de eficiencia actualizada con éxito. Revisa el nuevo diseño Dragon Ball Neón.",
        "fecha": "2026-07-24"
    }
]

def obtener_o_crear_carpeta_usuario(nombre_usuario):
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
        print(f"Error al gestionar carpeta Drive: {e}")
        return None

def generar_nombre_correlativo(folder_id):
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = drive_service.files().list(q=query, fields="files(name)").execute()
        files = results.get('files', [])
        numero_calculo = len(files) + 1
        return f"calculo{numero_calculo:06d}-{datetime.now().strftime('%d-%m-2026')}"
    except:
        return f"calculo000001-{datetime.now().strftime('%d-%m-2026')}"

def crear_pdf_en_memoria(datos_extensos):
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "VEKTOR NEXUS - REPORTE DE PRODUCCIÓN")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, f"Fecha: {datetime.now().strftime('%d/%m/2026 %H:%M')}")
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
    img = Image.new('RGB', (600, 300), color='#090a16')
    d = ImageDraw.Draw(img)
    d.text((30, 30), "VEKTOR NEXUS - RESUMEN DE CÁLCULO", fill='#00f3ff')
    d.line([(30, 55), (570, 55)], fill='#ff007f', width=2)
    y = 80
    for linea in datos_cortos:
        d.text((30, y), str(linea), fill='#ffffff')
        y += 30
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer

def cargar_usuarios_drive():
    try:
        records = sheet.get_all_values()
        usuarios = {}
        for row in records[1:]:
            if len(row) > 0 and str(row[0]).strip():
                tkn = str(row[0]).strip()
                is_hibernated = str(row[6]).lower() == 'false' if len(row) > 6 and row[6] != "" else False
                usuarios[tkn] = {
                    "token": tkn,
                    "nombre": str(row[1]).strip() if len(row) > 1 else "Usuario Nexus",
                    "contacto": str(row[2]).strip() if len(row) > 2 else "",
                    "pin": str(row[3]).strip() if len(row) > 3 else "0000",
                    "rol": str(row[4]).strip() if len(row) > 4 else "operador",
                    "device_id": str(row[5]).strip() if len(row) > 5 else "",
                    "ultima_conexion": str(row[11]).strip() if len(row) > 11 else "Desconocida",
                    "permisos": {
                        "biohorario": not is_hibernated,
                        "eficiencia": str(row[7]).lower() == 'true' if len(row) > 7 and row[7] != "" else True,
                        "tiempo": str(row[8]).lower() == 'true' if len(row) > 8 and row[8] != "" else True,
                        "metas": str(row[9]).lower() == 'true' if len(row) > 9 and row[9] != "" else True,
                        "historial": str(row[10]).lower() == 'true' if len(row) > 10 and row[10] != "" else True
                    }
                }
        # Garantizar Admin Angel0301 siempre presente
        if "angel0301" not in usuarios:
            usuarios["angel0301"] = {
                "token": "angel0301",
                "nombre": "Angel Castillo",
                "contacto": "Admin Principal",
                "pin": "2004",
                "rol": "admin",
                "device_id": "",
                "ultima_conexion": "Ahora",
                "permisos": {"biohorario": True, "eficiencia": True, "tiempo": True, "metas": True, "historial": True}
            }
        return usuarios
    except Exception as e:
        print("Error al leer usuarios:", e)
        return {
            "angel0301": {
                "token": "angel0301", "nombre": "Angel Castillo", "contacto": "Admin", "pin": "2004",
                "rol": "admin", "device_id": "", "ultima_conexion": "Ahora",
                "permisos": {"biohorario": True, "eficiencia": True, "tiempo": True, "metas": True, "historial": True}
            }
        }

@app.route('/')
def index():
    # Enlace general único sin requerir token en la URL
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login_verificar():
    data = request.json or {}
    token_ingresado = str(data.get('token')).strip()
    pin_ingresado = str(data.get('pin')).strip()
    
    usuarios_actuales = cargar_usuarios_drive()
    
    if token_ingresado in usuarios_actuales:
        u = usuarios_actuales[token_ingresado]
        if str(u['pin']).strip() == pin_ingresado:
            session['user_token'] = token_ingresado
            session['user_name'] = u['nombre']
            return jsonify({
                "status": "success",
                "user": u,
                "comunicados": comunicados_vip
            })
    return jsonify({"status": "error", "message": "Token o PIN Incorrecto"}), 401

@app.route('/api/metas/datos', methods=['GET'])
def obtener_metas_datos():
    return jsonify({
        "status": "success",
        "datos": pdf_metas_cache["datos"],
        "estilos": pdf_metas_cache["estilos"],
        "tallas": pdf_metas_cache["tallas"],
        "procesos": pdf_metas_cache["procesos"]
    })

@app.route('/api/comunicados/crear', methods=['POST'])
def crear_comunicado():
    data = request.json or {}
    titulo = data.get('titulo')
    mensaje = data.get('mensaje')
    if not titulo or not mensaje:
        return jsonify({"status": "error", "message": "Datos de comunicado incompletos"}), 400
    
    nuevo_comunicado = {
        "id": len(comunicados_vip) + 1,
        "titulo": str(titulo).upper(),
        "mensaje": str(mensaje),
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    comunicados_vip.insert(0, nuevo_comunicado)
    return jsonify({"status": "success", "comunicado": nuevo_comunicado})

@app.route('/api/historial/guardar', methods=['POST'])
def guardar_calculo():
    data = request.json or {}
    token = data.get('token')
    lineas_calculo = data.get('lineas')

    if not token or not lineas_calculo:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400

    usuarios = cargar_usuarios_drive()
    if token not in usuarios:
        return jsonify({"status": "error", "message": "Usuario no válido"}), 403

    nombre_usuario = usuarios[token]['nombre']
    folder_id = obtener_o_crear_carpeta_usuario(nombre_usuario)
    if not folder_id:
        return jsonify({"status": "error", "message": "Error con carpeta Drive"}), 500

    nombre_base = generar_nombre_correlativo(folder_id)
    if len(lineas_calculo) > 5:
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
            "drive_url": uploaded_file.get('webViewLink')
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/admin/usuarios', methods=['GET', 'POST'])
def admin_usuarios():
    if request.method == 'GET':
        return jsonify(cargar_usuarios_drive())
    data = request.json or {}
    nuevo_token = "nexus_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    nuevo_pin = "".join(random.choices(string.digits, k=4))
    try:
        sheet.append_row([nuevo_token, data.get('nombre'), data.get('contacto'), nuevo_pin, "operador", "", "true", "true", "true", "true", "true", ""])
        return jsonify({"status": "success", "token": nuevo_token, "pin": nuevo_pin})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
