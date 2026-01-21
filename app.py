from flask import Flask, render_template, request, send_file, after_this_request
import os
from processor import KMZProcessor
from gh_manager import upload_to_github
import tempfile
import uuid

app = Flask(__name__)

# CONFIGURACIÓN (Establece estas variables en Render)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") 
GITHUB_REPO = os.environ.get("GITHUB_REPO") # Ej: "mi-usuario/mi-repo-datos"

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    if 'kmz_file' not in request.files:
        return "No se subió ningún archivo", 400
    
    file = request.files['kmz_file']
    if file.filename == '':
        return "Nombre de archivo vacío", 400

    # Usar directorios temporales (Render no tiene almacenamiento persistente)
    with tempfile.TemporaryDirectory() as temp_dir:
        input_filename = f"input_{uuid.uuid4().hex}.kmz"
        output_filename = f"processed_{uuid.uuid4().hex}.dxf"
        
        input_path = os.path.join(temp_dir, input_filename)
        output_path = os.path.join(temp_dir, output_filename)
        
        # 1. Guardar archivo subido localmente en temporal
        file.save(input_path)
        
        # 2. Subir Original a GitHub (Carpeta 'inputs')
        if GITHUB_TOKEN and GITHUB_REPO:
            upload_to_github(input_path, f"inputs/{file.filename}", GITHUB_REPO, GITHUB_TOKEN)
        
        # 3. Procesar
        try:
            processor = KMZProcessor()
            processor.process_file(input_path, output_path)
        except Exception as e:
            return f"Error en el procesamiento: {str(e)}", 500

        # 4. Subir Resultado a GitHub (Carpeta 'outputs')
        final_dxf_name = file.filename.replace('.kmz', '.dxf').replace('.KMZ', '.dxf')
        if GITHUB_TOKEN and GITHUB_REPO:
            upload_to_github(output_path, f"outputs/{final_dxf_name}", GITHUB_REPO, GITHUB_TOKEN)

        # 5. Enviar archivo al usuario para descargar
        # after_this_request asegura que no intentemos borrar antes de enviar, 
        # aunque con TemporaryDirectory se borra al salir del bloque, send_file necesita leerlo.
        # En este caso, enviamos directamente desde la ruta.
        return send_file(output_path, as_attachment=True, download_name=final_dxf_name)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
