from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import random
import json
import uuid
from datetime import datetime
from xhtml2pdf import pisa
from io import BytesIO
import qrcode
import base64
import matplotlib.pyplot as plt
import matplotlib
import re
from typing import Any, Dict

# importar el orquestador de agentes
try:
	from src.agents.agents_factory import run_agent_flow
except Exception:
	# fallback si se ejecuta desde diferente cwd
	try:
		from agents.agents_factory import run_agent_flow
	except Exception:
		run_agent_flow = None


# Rutas de directorios relativas a este archivo (app/main.py)
BASE_DIR = Path(__file__).resolve().parent  # app/
TEMPLATES_DIR = BASE_DIR.parent / "templates"  # ../templates
STATIC_DIR = BASE_DIR.parent / "static"  # ../static
PDF_DIR = BASE_DIR.parent / "generated_pdfs"  # ../generated_pdfs
DATA_DIR = BASE_DIR.parent / "data"  # ../data
PDF_METADATA_FILE = DATA_DIR / "pdf_metadata.json"

# Crear directorios si no existen
PDF_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


app = FastAPI(title="hackathon_ia")


# Montar archivos estáticos si existen
if STATIC_DIR.exists():
	app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Configurar Jinja2 para servir plantillas desde ../templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
	"""Devuelve `index.html` tal cual (archivo estático) para evitar que Jinja2 interpete sintaxis de React/JSX."""
	index_path = TEMPLATES_DIR / "index.html"
	if not index_path.exists():
		return HTMLResponse(content="<h1>404 Not Found</h1>", status_code=404)
	return FileResponse(path=str(index_path), media_type="text/html")


@app.get("/ping")
async def ping():
	return {"status": "ok"}


# Modelo para las peticiones del chat
class ChatRequest(BaseModel):
	message: str


# Modelo para las respuestas del chat
class ChatResponse(BaseModel):
	response: str


# Modelo para crear un PDF desde HTML
class PDFCreateRequest(BaseModel):
	html_content: str
	title: str = "Documento"
	description: str = ""
	percentage: float = 0.0

# Modelo para la respuesta de creación de PDF
class PDFCreateResponse(BaseModel):
	pdf_id: str
	download_url: str
	view_url: str
	filename: str
	created_at: str


# Modelo para listado de PDFs
class PDFListItem(BaseModel):
	pdf_id: str
	title: str
	description: str
	filename: str
	download_url: str
	view_url: str
	created_at: str


# Funciones auxiliares para manejo de metadatos de PDFs
def load_pdf_metadata():
	"""Carga los metadatos de PDFs desde el archivo JSON"""
	if not PDF_METADATA_FILE.exists():
		return []
	try:
		with open(PDF_METADATA_FILE, 'r', encoding='utf-8') as f:
			return json.load(f)
	except Exception as e:
		print(f"Error loading PDF metadata: {e}")
		return []


def save_pdf_metadata(metadata_list):
	"""Guarda los metadatos de PDFs en el archivo JSON"""
	try:
		with open(PDF_METADATA_FILE, 'w', encoding='utf-8') as f:
			json.dump(metadata_list, f, ensure_ascii=False, indent=2)
		return True
	except Exception as e:
		print(f"Error saving PDF metadata: {e}")
		return False


def add_pdf_metadata(pdf_id, title, description, filename):
	"""Agrega un nuevo registro de PDF a los metadatos"""
	metadata_list = load_pdf_metadata()
	new_entry = {
		"pdf_id": pdf_id,
		"title": title,
		"description": description,
		"filename": filename,
		"download_url": f"/api/pdf/{pdf_id}/download",
		"view_url": f"/api/pdf/{pdf_id}/view",
		"created_at": datetime.now().isoformat()
	}
	metadata_list.append(new_entry)
	save_pdf_metadata(metadata_list)
	return new_entry


def generate_qr_code(url: str) -> str:
	"""
	Genera un código QR para la URL proporcionada y lo retorna como base64.
	
	Args:
		url: URL para la que se generará el código QR
		
	Returns:
		String base64 del código QR en formato PNG
	"""
	# Crear código QR
	qr = qrcode.QRCode(
		version=1,
		error_correction=qrcode.constants.ERROR_CORRECT_L,
		box_size=10,
		border=4,
	)
	qr.add_data(url)
	qr.make(fit=True)
	
	# Generar imagen
	img = qr.make_image(fill_color="black", back_color="white")
	
	# Convertir a base64
	buffer = BytesIO()
	img.save(buffer, format='PNG')
	buffer.seek(0)
	img_base64 = base64.b64encode(buffer.read()).decode()
	
	return img_base64


def generate_circular_chart(percentage: float, title: str = "Progreso") -> str:
	"""
	Genera un gráfico circular (donut chart) para mostrar un porcentaje.
	
	Args:
		percentage: Valor del porcentaje (0-100)
		title: Título del gráfico
		
	Returns:
		String base64 del gráfico en formato PNG
	"""
	# Configurar matplotlib para no usar GUI
	matplotlib.use('Agg')
	
	# Asegurar que el porcentaje esté en el rango correcto
	percentage = max(0, min(100, percentage))
	remaining = 100 - percentage
	
	# Crear figura con fondo transparente
	fig, ax = plt.subplots(figsize=(6, 6), facecolor='white')
	
	# Datos para el gráfico
	sizes = [percentage, remaining]
	colors = ['#4CAF50', '#E8E8E8']  # Verde para completado, gris claro para restante
	explode = (0.05, 0)  # Resaltar la sección del porcentaje
	
	# Crear el gráfico circular (donut)
	wedges, texts, autotexts = ax.pie(
		sizes,
		explode=explode,
		colors=colors,
		autopct='',
		startangle=90,
		wedgeprops=dict(width=0.4, edgecolor='white', linewidth=2)
	)
	
	# Agregar el porcentaje en el centro
	ax.text(0, 0, f'{percentage:.1f}%', 
			ha='center', va='center', 
			fontsize=48, fontweight='bold', 
			color='#333333')
	
	# Agregar título arriba del gráfico
	ax.text(0, -1.4, title, 
			ha='center', va='center', 
			fontsize=18, fontweight='bold', 
			color='#555555')
	
	# Asegurar que el gráfico sea circular
	ax.axis('equal')
	
	# Guardar en buffer
	buffer = BytesIO()
	plt.tight_layout()
	plt.savefig(buffer, format='PNG', dpi=150, bbox_inches='tight', 
				facecolor='white', edgecolor='none')
	plt.close(fig)
	
	# Convertir a base64
	buffer.seek(0)
	img_base64 = base64.b64encode(buffer.read()).decode()
	
	return img_base64


def add_chart_to_html(html_content: str, percentage: float, chart_title: str = "Nivel de Riesgo") -> str:
	"""
	Agrega un gráfico circular al inicio del contenido HTML.
	
	Args:
		html_content: Contenido HTML original
		percentage: Porcentaje para mostrar (0-100)
		chart_title: Título del gráfico
		
	Returns:
		HTML con el gráfico agregado al inicio
	"""
	# Generar gráfico circular
	chart_base64 = generate_circular_chart(percentage, chart_title)
	
	# HTML del gráfico centrado al inicio del documento
	chart_html = f"""
	<!DOCTYPE html>
	<html>
	<head>
		<meta charset="utf-8">
		<style>
			body {{
				font-family: Arial, sans-serif;
				margin: 20px;
			}}
			.chart-container {{
				text-align: center;
				margin: 30px auto 50px;
				padding: 20px;
			}}
			.chart-container img {{
				max-width: 400px;
				height: auto;
			}}
		</style>
	</head>
	<body>
		<div class="chart-container">
			<img src="data:image/png;base64,{chart_base64}" alt="Gráfico Circular">
		</div>
	"""
	
	# Limpiar el HTML original de etiquetas de documento si las tiene
	content = html_content
	if '<!DOCTYPE' in content:
		# Extraer solo el contenido del body
		import re
		body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
		if body_match:
			content = body_match.group(1)
		else:
			# Si no hay body, quitar html, head, body tags
			content = re.sub(r'<html[^>]*>|</html>|<head[^>]*>.*?</head>|<body[^>]*>|</body>', '', content, flags=re.DOTALL | re.IGNORECASE)
	
	# Combinar gráfico con contenido
	return chart_html + content


def add_qr_to_html(html_content: str, pdf_url: str) -> str:
	"""
	Agrega un código QR al final del contenido HTML.
	
	Args:
		html_content: Contenido HTML original
		pdf_url: URL completa del PDF para generar el QR
		
	Returns:
		HTML con el código QR agregado al final
	"""
	# Generar código QR
	qr_base64 = generate_qr_code(pdf_url)
	
	# HTML del código QR centrado al final del documento
	qr_html = f"""
	<div style="page-break-before: avoid; margin-top: 50px; padding-top: 30px; border-top: 2px solid #e0e0e0; text-align: center;">
		<h3 style="color: #666; font-size: 16px; margin-bottom: 20px;">Accede a este documento escaneando el código QR</h3>
		<img src="data:image/png;base64,{qr_base64}" alt="QR Code" style="width: 200px; height: 200px; margin: 0 auto; display: block;">
		<p style="margin-top: 15px; font-size: 12px; color: #888;">Escanea este código para ver el PDF en línea</p>
	</div>
	</body>
	</html>
	"""
	
	# Reemplazar el cierre de body y html con el QR incluido
	if '</body>' in html_content and '</html>' in html_content:
		html_content = html_content.replace('</body>', '').replace('</html>', '')
		html_content += qr_html
	else:
		# Si no hay cierre de etiquetas, agregar al final
		html_content += qr_html
	
	return html_content


# API endpoint para el chatbot (demo hardcodeado)
# Modelo para las peticiones del chat
class ChatRequest(BaseModel):
	message: str


# Modelo para las respuestas del chat
class ChatResponse(BaseModel):
	response: str


def format_response_to_html(text: str) -> str:
    """
    Convierte texto con formato simple o sin formato a HTML estructurado.
    """
    html = text
    
    # --- 1. Búsqueda de formato explícito --- 
    has_explicit_format = False
    if html.startswith('[Title: ') or "**" in html:
        has_explicit_format = True

    if has_explicit_format:
        if html.startswith('[Title: '):
            title_end = html.find(']')
            if title_end != -1:
                title = html[8:title_end]
                html = html[title_end+1:].strip()
                html = f"<h3>{title}</h3>{html}"

        html = html.replace("**Introducción**", "<h4>Introducción</h4>")
        html = html.replace("**Tipos de Diabetes**", "<h4>Tipos de Diabetes</h4>")
        html = html.replace("**Complicaciones**", "<h4>Complicaciones</h4>")
        html = html.replace("**Diagnóstico**", "<h4>Diagnóstico</h4>")
        html = html.replace("**Prevención y Control**", "<h4>Prevención y Control</h4>")
        
        parts = html.split("<h4>")
        processed_html = ""
        if parts:
            first_part = parts[0]
            h3_end_index = first_part.find("</h3>")
            if h3_end_index != -1:
                processed_html += first_part[:h3_end_index+5]
                remaining_text = first_part[h3_end_index+5:].strip()
                if remaining_text:
                    processed_html += f"<p>{remaining_text}</p>"
            elif first_part.strip():
                processed_html += f"<p>{first_part.strip()}</p>"

            for part in parts[1:]:
                h4_end_index = part.find("</h4>")
                if h4_end_index != -1:
                    title = part[:h4_end_index]
                    content = part[h4_end_index+5:].strip()
                    processed_html += f"<h4>{title}</h4>"
                    if content:
                        processed_html += f"<p>{content}</p>"
        return processed_html

    # --- 2. Búsqueda de palabras clave si no hay formato explícito ---
    keywords = ["Introducción", "Tipos de Diabetes", "Síntomas", "Diagnóstico", "Complicaciones", "Tratamiento"]
    temp_html = html
    found_keywords = False

    # Ordenar keywords por longitud para evitar matching parcial (ej. "Tipos" vs "Tipos de Diabetes")
    keywords.sort(key=len, reverse=True)

    for keyword in keywords:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, temp_html, re.IGNORECASE):
            found_keywords = True
            temp_html = re.sub(pattern, f"---section---{keyword}", temp_html, count=1, flags=re.IGNORECASE)

    if found_keywords:
        processed_html = "<h3>Información sobre Diabetes</h3>"
        sections = temp_html.split('---section---')
        
        if sections[0].strip():
            processed_html += f"<p>{sections[0].strip()}</p>"
            
        for section_content in sections[1:]:
            section_content = section_content.strip()
            found_title = None
            
            for keyword in keywords:
                if section_content.lower().startswith(keyword.lower()):
                    actual_title = section_content[:len(keyword)]
                    remaining_content = section_content[len(keyword):].strip()
                    
                    processed_html += f"<h4>{actual_title}</h4>"
                    if remaining_content:
                        processed_html += f"<p>{remaining_content}</p>"
                    found_title = True
                    break
            
            if not found_title and section_content:
                processed_html += f"<p>{section_content}</p>"
        return processed_html

    # --- 3. Fallback: sin formato y sin palabras clave ---
    return f"<h3>Información</h3><p>{text}</p>"


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint de chatbot que utiliza el flujo de agentes para generar respuestas.
    """
    if run_agent_flow is None:
        return ChatResponse(response="Error: El flujo de agentes no está disponible.")

    try:
        out = run_agent_flow(request.message)
        raw_response = out.get('final', 'Lo siento, no pude generar una respuesta.')
        formatted_response = format_response_to_html(raw_response)
        return ChatResponse(response=formatted_response)
    except Exception as e:
        return ChatResponse(response=f"Error: {e}")


import sys
from pathlib import Path

# Agregar el directorio raíz al path de Python
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from api import coach

app.include_router(coach.router, prefix="/api/coach", tags=["coach"])


# ========== Endpoints para manejo de PDFs ==========

@app.post("/api/pdf/create", response_model=PDFCreateResponse)
async def create_pdf(request: PDFCreateRequest, req: Request):
	"""
	Crea un PDF desde contenido HTML y lo guarda.
	Retorna URLs para descargar y visualizar el PDF.
	"""
	try:
		# Generar un ID único para el PDF
		pdf_id = str(uuid.uuid4())
		filename = f"{pdf_id}.pdf"
		pdf_path = PDF_DIR / filename
		
		# Construir URL completa del PDF
		base_url = str(req.base_url).rstrip('/')
		pdf_view_url = f"{base_url}/api/pdf/{pdf_id}/view"
		
		# Agregar gráfico circular al inicio del HTML si se proporciona un porcentaje
		html_content = request.html_content
		if request.percentage > 0:
			html_content = add_chart_to_html(html_content, request.percentage, f"{request.title} - Análisis")
		
		# Agregar código QR al final del HTML
		html_with_qr = add_qr_to_html(html_content, pdf_view_url)
		
		# Convertir HTML a PDF usando xhtml2pdf
		with open(pdf_path, "wb") as pdf_file:
			pisa_status = pisa.CreatePDF(
				html_with_qr.encode('utf-8'),
				dest=pdf_file
			)
		
		if pisa_status.err:
			raise Exception(f"Error al generar PDF: {pisa_status.err}")
		
		# Guardar metadatos
		metadata = add_pdf_metadata(
			pdf_id=pdf_id,
			title=request.title,
			description=request.description,
			filename=filename
		)
		
		return PDFCreateResponse(
			pdf_id=pdf_id,
			download_url=metadata["download_url"],
			view_url=metadata["view_url"],
			filename=filename,
			created_at=metadata["created_at"]
		)
	
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error al crear PDF: {str(e)}")


@app.get("/api/pdf/{pdf_id}/download")
async def download_pdf(pdf_id: str):
	"""
	Descarga un PDF por su ID
	"""
	# Buscar el PDF en los metadatos
	metadata_list = load_pdf_metadata()
	pdf_metadata = next((item for item in metadata_list if item["pdf_id"] == pdf_id), None)
	
	if not pdf_metadata:
		raise HTTPException(status_code=404, detail="PDF no encontrado")
	
	pdf_path = PDF_DIR / pdf_metadata["filename"]
	
	if not pdf_path.exists():
		raise HTTPException(status_code=404, detail="Archivo PDF no existe")
	
	return FileResponse(
		path=str(pdf_path),
		media_type="application/pdf",
		filename=pdf_metadata["filename"],
		headers={"Content-Disposition": f'attachment; filename="{pdf_metadata["title"]}.pdf"'}
	)


@app.get("/api/pdf/{pdf_id}/view")
async def view_pdf(pdf_id: str):
	"""
	Visualiza un PDF en el navegador por su ID
	"""
	# Buscar el PDF en los metadatos
	metadata_list = load_pdf_metadata()
	pdf_metadata = next((item for item in metadata_list if item["pdf_id"] == pdf_id), None)
	
	if not pdf_metadata:
		raise HTTPException(status_code=404, detail="PDF no encontrado")
	
	pdf_path = PDF_DIR / pdf_metadata["filename"]
	
	if not pdf_path.exists():
		raise HTTPException(status_code=404, detail="Archivo PDF no existe")
	
	return FileResponse(
		path=str(pdf_path),
		media_type="application/pdf",
		headers={"Content-Disposition": f'inline; filename="{pdf_metadata["title"]}.pdf"'}
	)


@app.get("/api/pdf/list", response_model=list[PDFListItem])
async def list_pdfs():
	"""
	Lista todos los PDFs disponibles con sus metadatos
	"""
	metadata_list = load_pdf_metadata()
	return [PDFListItem(**item) for item in metadata_list]


@app.get("/api/pdf/{pdf_id}/info")
async def get_pdf_info(pdf_id: str):
	"""
	Obtiene información detallada de un PDF específico
	"""
	metadata_list = load_pdf_metadata()
	pdf_metadata = next((item for item in metadata_list if item["pdf_id"] == pdf_id), None)
	
	if not pdf_metadata:
		raise HTTPException(status_code=404, detail="PDF no encontrado")
	
	# Verificar si el archivo existe
	pdf_path = PDF_DIR / pdf_metadata["filename"]
	file_exists = pdf_path.exists()
	
	return {
		**pdf_metadata,
		"file_exists": file_exists,
		"file_size_bytes": pdf_path.stat().st_size if file_exists else 0
	}


@app.delete("/api/pdf/{pdf_id}")
async def delete_pdf(pdf_id: str):
	"""
	Elimina un PDF y sus metadatos
	"""
	metadata_list = load_pdf_metadata()
	pdf_metadata = next((item for item in metadata_list if item["pdf_id"] == pdf_id), None)
	
	if not pdf_metadata:
		raise HTTPException(status_code=404, detail="PDF no encontrado")
	
	# Eliminar archivo físico
	pdf_path = PDF_DIR / pdf_metadata["filename"]
	if pdf_path.exists():
		pdf_path.unlink()
	
	# Eliminar de metadatos
	updated_metadata = [item for item in metadata_list if item["pdf_id"] != pdf_id]
	save_pdf_metadata(updated_metadata)
	
	return {"message": "PDF eliminado exitosamente", "pdf_id": pdf_id}


if __name__ == "__main__":
	# Permite ejecutar `python app/main.py` para desarrollo local
	uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
