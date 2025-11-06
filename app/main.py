from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import random


# Rutas de directorios relativas a este archivo (app/main.py)
BASE_DIR = Path(__file__).resolve().parent  # app/
TEMPLATES_DIR = BASE_DIR.parent / "templates"  # ../templates
STATIC_DIR = BASE_DIR.parent / "static"  # ../static


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


if __name__ == "__main__":
	# Permite ejecutar `python app/main.py` para desarrollo local
	uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
