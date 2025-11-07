# Asesor Médico IA

Asesor Médico IA es un proyecto que utiliza una combinación de agentes para proporcionar asesoramiento médico basado en las consultas de los usuarios. El proyecto está construido con FastAPI y utiliza LangChain para el pipeline de agentes.

## Cómo empezar

Estas instrucciones te permitirán obtener una copia del proyecto en funcionamiento en tu máquina local para fines de desarrollo y pruebas.

### Prerrequisitos

- Docker
- Docker Compose

### Instalación

1. Clona el repositorio
   ```sh
   git clone https://github.com/tu_usuario/hackathon_ia.git
   ```
2. Crea un archivo `.env` en la raíz del proyecto y agrega tu clave de API de OpenAI:
   ```
   OPENAI_API_KEY=tu_clave_de_api_de_openai
   ```
3. Construye y ejecuta el contenedor de Docker:
   ```sh
   docker-compose up --build -d
   ```

La aplicación estará disponible en `http://localhost:8000`.

## Uso

La aplicación proporciona una interfaz web para interactuar con el asesor médico. Puedes hacer preguntas y la IA te proporcionará respuestas basadas en su base de conocimientos.

Para ver la documentación de la API, visita `http://localhost:8000/docs`.

## Dependencias

El proyecto utiliza las siguientes dependencias:

- fastapi==0.121.0
- Jinja2==3.1.6
- langgraph==1.0.2
- pydantic==2.12.4
- uvicorn==0.38.0
- openai>=1.0.0
- PyPDF2>=3.0.0
- python-dotenv>=1.0.0
- numpy>=1.23.0
- markdown>=3.4.0
- bleach>=6.0.0