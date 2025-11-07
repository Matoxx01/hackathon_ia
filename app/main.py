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
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
	"""
	Endpoint de chatbot con respuestas hardcodeadas para demostración.
	"""
	message = request.message.lower()
	
	# Respuestas predefinidas basadas en palabras clave
	responses = {
		"hola": "¡Hola! 👋 Soy MediNutrIA, tu asistente de salud y nutrición. Estoy aquí para ayudarte con recomendaciones nutricionales y de bienestar. ¿En qué puedo ayudarte hoy?",
		"ayuda": "Puedo ayudarte con:\n• Recomendaciones nutricionales personalizadas\n• Consejos de alimentación saludable\n• Información sobre vitaminas y minerales\n• Planes de comidas equilibradas\n• Consejos de hidratación\n¿Sobre qué tema te gustaría saber más?",
		"dieta": "Para una dieta equilibrada, te recomiendo:\n• Consumir 5 porciones de frutas y verduras al día 🥗\n• Incluir proteínas magras (pollo, pescado, legumbres) 🐟\n• Preferir cereales integrales 🌾\n• Beber al menos 2 litros de agua diarios 💧\n• Limitar el consumo de azúcares y grasas saturadas\n¿Tienes alguna preferencia alimentaria específica?",
		"agua": "¡Excelente pregunta! 💧 La hidratación es fundamental:\n• Bebe al menos 8 vasos de agua al día (aproximadamente 2 litros)\n• Aumenta la ingesta durante ejercicio o clima caluroso\n• El agua ayuda a la digestión, circulación y temperatura corporal\n• Puedes incluir infusiones sin azúcar\n¿Sueles tener problemas para beber suficiente agua?",
		"ejercicio": "¡Muy bien! El ejercicio es clave para la salud 💪\n• Se recomienda al menos 150 minutos de actividad moderada por semana\n• Incluye ejercicios cardiovasculares y de fuerza\n• Comienza gradualmente si eres principiante\n• No olvides calentar antes y estirar después\n• Combínalo con una buena alimentación para mejores resultados\n¿Qué tipo de ejercicio te gustaría realizar?",
		"vitaminas": "Las vitaminas son esenciales para tu salud:\n• Vitamina C: Cítricos, fresas, pimientos 🍊\n• Vitamina D: Sol, pescado graso, huevos ☀️\n• Vitamina A: Zanahorias, espinacas, batatas 🥕\n• Vitaminas B: Cereales integrales, legumbres, frutos secos\n• Vitamina E: Frutos secos, semillas, aceite de oliva\n¿Te interesa saber sobre alguna vitamina en particular?",
		"peso": "Para un control de peso saludable:\n• Mantén un déficit calórico moderado (no extremo)\n• Come porciones adecuadas, mastica despacio\n• No te saltes comidas, especialmente el desayuno\n• Prioriza alimentos nutritivos sobre calorías vacías\n• Combina alimentación con ejercicio regular\n• Consulta con un profesional para un plan personalizado\nRecuerda: lo importante es la salud, no solo el número en la báscula.",
		"diabetes": "Para el manejo de la diabetes:\n• Controla el consumo de carbohidratos\n• Prefiere carbohidratos complejos y fibra\n• Come a horarios regulares\n• Monitorea tu glucosa regularmente\n• Mantén un peso saludable\n• Ejercicio regular ayuda a controlar glucosa\n⚠️ Importante: Sigue siempre las indicaciones de tu médico y endocrinólogo.",
		"desayuno": "Un desayuno saludable podría incluir:\n• Avena con frutas y frutos secos 🥣\n• Huevos revueltos con verduras y pan integral 🍳\n• Yogur natural con frutas y granola\n• Tostadas integrales con aguacate y tomate 🥑\n• Batido de frutas con proteína\nEl desayuno te da energía para comenzar el día. ¿Cuál te gustaría probar?",
		"sueño": "El buen descanso es fundamental para la salud:\n• Duerme 7-9 horas diariamente 😴\n• Mantén horarios regulares de sueño\n• Evita pantallas 1 hora antes de dormir\n• Cena ligero, al menos 2 horas antes de acostarte\n• Mantén tu habitación oscura y fresca\n• Evita cafeína después de las 16:00\n¿Tienes problemas para dormir?",
	}
	
	# Buscar respuesta basada en palabras clave
	response = None
	for keyword, answer in responses.items():
		if keyword in message:
			response = answer
			break
	
	# Respuesta por defecto si no hay coincidencias
	if not response:
		default_responses = [
			"Entiendo tu pregunta. Como asistente de salud y nutrición, te recomiendo consultar con un profesional médico para casos específicos. ¿Hay algo sobre nutrición general en lo que pueda ayudarte?",
			"Esa es una buena pregunta. Puedo ayudarte con información general sobre nutrición, dietas saludables, hidratación, vitaminas y hábitos de vida saludable. ¿Te gustaría saber sobre alguno de estos temas?",
			"Interesante pregunta. Para brindarte la mejor información, ¿podrías ser más específico? Puedo ayudarte con temas de nutrición, alimentación balanceada, hidratación o hábitos saludables.",
			"Gracias por tu consulta. Estoy aquí para ayudarte con recomendaciones nutricionales y de bienestar general. ¿Te gustaría saber sobre alimentación saludable, control de peso o vitaminas?",
		]
		response = random.choice(default_responses)
	
	return ChatResponse(response=response)


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
		
		# Agregar código QR al HTML
		html_with_qr = add_qr_to_html(request.html_content, pdf_view_url)
		
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
