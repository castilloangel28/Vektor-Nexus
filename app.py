from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import random
import string
import io
import openpyxl
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'angel_admin_2026_secure')

CARPETA_RAIZ_DRIVE = "1PbH8767Q86O-TntoxDxozaGiBl3WJqE0"

# --- DB Y CREADENCIALES ---[cite: 2]
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open("Base_Datos_Calculadora").sheet1
    drive_service = build('drive', 'v3', credentials=creds)
except Exception as e:
    print(f"Error de conexión a Google: {e}")

# Módulo VIP de Comunicados
comunicado_global = {"mensaje": "¡Bienvenidos al sistema actualizado!", "autor": "Admin"}

# (Mantener aquí tus Helper Functions: obtener_o_crear_carpeta_usuario, generar_nombre_correlativo, crear_pdf, crear_imagen, cargar_usuarios_drive tal cual las tienes)[cite: 2]

# --- RUTAS DE API ACTUALIZADAS ---

@app.route('/')
def index():
    # Enlace general: Ya no verifica el token por URL[cite: 2]
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login_verificar():
    data = request.json
    token = str(data.get('token')).strip()
    pin_ingresado = str(data.get('pin')).strip()
    device_id_cliente = str(data.get('device_id')).strip()

    usuarios_actuales = cargar_usuarios_drive()
    # Verifica tanto token en columna A como PIN en columna D[cite: 2]
    if token in usuarios_actuales and str(usuarios_actuales[token]['pin']).strip() == pin_ingresado:
        session['user_token'] = token
        session['user_name'] = usuarios_actuales[token]['nombre']
        
        # Validar VIP
        es_vip = token in ['angel0301', 'karina827']
        
        return jsonify({
            "status": "success", 
            "nombre": usuarios_actuales[token]['nombre'],
            "rol": usuarios_actuales[token]['rol'],
            "permisos": usuarios_actuales[token]['permisos'],
            "comunicado": comunicado_global,
            "vip": es_vip
        })
    return jsonify({"status": "error", "message": "Credenciales Incorrectas"}), 401

@app.route('/api/comunicados', methods=['POST'])
def actualizar_comunicado():
    data = request.json
    if data.get('token') in ['angel0301', 'karina827']:
        comunicado_global["mensaje"] = data.get('mensaje')
        comunicado_global["autor"] = data.get('autor')
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 403

# (Mantener el resto de endpoints: /api/metas/datos, /api/historial/guardar, /api/admin/usuarios idénticos)[cite: 2]

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
