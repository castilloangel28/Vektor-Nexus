import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# Endpoint de verificación de estado servidor
@app.route('/', methods=['GET'])
def status():
    return jsonify({
        "status": "Online",
        "system": "VEKTOR NEXUS V4.5 - CONTROL INDUSTRIAL",
        "author": "Angel Castillo"
    }), 200

# Endpoint para sincronización de Metas / Google Drive Sheet (.xlsx)
@app.route('/api/sync-drive-metas', methods=['POST'])
def sync_drive_metas():
    try:
        data = request.json
        sheet_url = data.get("sheet_url")
        
        if not sheet_url:
            return jsonify({"error": "No se proporcionó la URL de Google Sheets"}), 400

        # Petición a la vista de exportación CSV de Google Sheets
        response = requests.get(sheet_url)
        if response.status_code == 200:
            lines = response.text.splitlines()
            metas = []
            
            # Parsear filas (Estilo, Talla, Proceso, Meta)
            for line in lines[1:]:
                cols = line.split(',')
                if len(cols) >= 4:
                    metas.append({
                        "estilo": cols[0].strip(),
                        "talla": cols[1].strip(),
                        "proceso": cols[2].strip(),
                        "meta": float(cols[3].strip()) if cols[3].strip().replace('.', '', 1).isdigit() else 0
                    })
                    
            return jsonify({
                "success": True,
                "count": len(metas),
                "data": metas
            }), 200
        else:
            return jsonify({"error": "No se pudo leer la hoja de Google Drive"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
