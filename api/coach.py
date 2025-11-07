from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
import html
import logging
import httpx
import uuid
import os

logger = logging.getLogger(__name__)

try:
    import markdown
    import bleach
except Exception:
    markdown = None
    bleach = None

import sys
from pathlib import Path

# Agregar el directorio raíz al path de Python
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv es opcional

try:
    from src.agents.agents_factory import run_agent_flow
except ImportError as e:
    logger.warning(f"Error importando agents_factory: {e}")
    run_agent_flow = None

try:
    from src.prediction_session import (
        get_or_create_session,
        get_session,
        get_next_question,
        process_answer,
        calculate_bmi,
        is_session_complete,
        VARIABLE_QUESTIONS
    )
    from api.predict import predict_diabetes_risk, get_risk_interpretation
    logger.info("Módulos de predicción importados correctamente")
except ImportError as e:
    logger.error(f"Error importando módulos de predicción: {e}")
    get_or_create_session = None
    get_session = None
    predict_diabetes_risk = None
    get_risk_interpretation = None

router = APIRouter()

class CoachRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    start_assessment: bool = False  # Flag para iniciar evaluación

class CoachResponse(BaseModel):
    risk: str
    retrieved_count: int
    draft: str
    final: str
    details: Dict[str, Any] | None = None
    session_id: Optional[str] = None
    is_question: bool = False  # Indica si es una pregunta de evaluación
    question_progress: Optional[str] = None  # Progreso de preguntas (ej: "3/12")

@router.post("/", response_model=CoachResponse)
async def coach_endpoint(request: CoachRequest):
    """
    Endpoint principal del coach que maneja:
    1. Conversación normal con el agente
    2. Inicio de evaluación de riesgo
    3. Recopilación de variables para predicción
    4. Predicción y recomendaciones personalizadas
    """
    
    # Detectar palabras clave para iniciar evaluación
    query_lower = request.query.lower()
    keywords_assessment = [
        "evaluar", "evaluación", "evalua", "evaluame", "riesgo", "predicción", "prediccion",
        "test", "cuestionario", "assessment", "analisis", "análisis",
        "quiero saber mi riesgo", "calculame", "calcular mi riesgo",
        "medir", "medirme", "medir mi riesgo", "quiero medir",
        "chequear", "chequeo", "revisar", "calcular", "calculame"
    ]
    
    should_start_assessment = (
        request.start_assessment or 
        any(keyword in query_lower for keyword in keywords_assessment)
    )
    
    # Log para debugging
    logger.info(f"📩 Query recibido: '{request.query}'")
    logger.info(f"🔍 should_start_assessment: {should_start_assessment}")
    logger.info(f"✅ get_or_create_session disponible: {get_or_create_session is not None}")
    
    # Si hay una sesión activa, continuar con el flujo de preguntas
    if request.session_id:
        if get_session is None:
            raise HTTPException(status_code=500, detail="Módulo de sesiones no disponible")
        session = get_session(request.session_id)
        if session and not session.completed:
            return await handle_assessment_flow(request, session)
    
    # Si se solicita iniciar evaluación
    if should_start_assessment:
        if get_or_create_session is None:
            raise HTTPException(status_code=500, detail="Módulo de evaluación no disponible")
        return await start_assessment()
    
    # Flujo normal del agente conversacional
    return await handle_normal_conversation(request)


async def start_assessment() -> CoachResponse:
    """Inicia una nueva sesión de evaluación de riesgo."""
    session = get_or_create_session()
    first_question = get_next_question(session)
    
    intro_html = render_markdown_to_safe_html(f"""
### 🩺 Evaluación de Riesgo de Diabetes

¡Perfecto! Voy a hacerte algunas preguntas para evaluar tu riesgo de diabetes de manera personalizada.

Son **{len(VARIABLE_QUESTIONS)} preguntas rápidas** sobre tu salud y estilo de vida. Al final, te daré:
- 📊 Tu nivel de riesgo (bajo, medio o alto)
- 📋 Recomendaciones personalizadas
- 💡 Pasos específicos a seguir

**Pregunta 1 de {len(VARIABLE_QUESTIONS)}:**

{first_question['question']}

{"**Opciones:** " + ", ".join(first_question['options']) if first_question.get('type') == 'choice' else ""}
""")
    
    return CoachResponse(
        risk="evaluacion",
        retrieved_count=0,
        draft="",
        final=intro_html,
        session_id=session.session_id,
        is_question=True,
        question_progress=f"1/{len(VARIABLE_QUESTIONS)}"
    )


async def handle_assessment_flow(request: CoachRequest, session) -> CoachResponse:
    """Maneja el flujo de preguntas y respuestas de la evaluación."""
    
    # Procesar la respuesta del usuario
    result = process_answer(session, request.query)
    
    if not result["success"]:
        # Error de validación, re-preguntar
        error_html = render_markdown_to_safe_html(f"""
❌ {result['message']}

**{result['next_question']['question']}**

{"**Opciones:** " + ", ".join(result['next_question']['options']) if result['next_question'].get('type') == 'choice' else ""}
""")
        return CoachResponse(
            risk="evaluacion",
            retrieved_count=0,
            draft="",
            final=error_html,
            session_id=session.session_id,
            is_question=True,
            question_progress=f"{session.current_question_index + 1}/{len(VARIABLE_QUESTIONS)}"
        )
    
    # Si hay siguiente pregunta
    if result["next_question"]:
        next_q = result["next_question"]
        progress_num = session.current_question_index + 1
        
        response_html = render_markdown_to_safe_html(f"""
✅ Respuesta registrada.

**Pregunta {progress_num} de {len(VARIABLE_QUESTIONS)}:**

{next_q['question']}

{"**Opciones:** " + ", ".join(next_q['options']) if next_q.get('type') == 'choice' else ""}
""")
        
        return CoachResponse(
            risk="evaluacion",
            retrieved_count=0,
            draft="",
            final=response_html,
            session_id=session.session_id,
            is_question=True,
            question_progress=f"{progress_num}/{len(VARIABLE_QUESTIONS)}"
        )
    
    # Si no hay más preguntas, realizar predicción
    return await complete_assessment(session)


async def generate_assessment_pdf(html_content: str, risk_level: str, risk_score: float, session) -> Optional[Dict[str, Any]]:
    """
    Genera un PDF del informe de evaluación usando la API interna.
    
    Args:
        html_content: Contenido HTML del informe
        risk_level: Nivel de riesgo (bajo, medio, alto)
        risk_score: Probabilidad de riesgo (0-1)
        session: Objeto de sesión con variables del usuario
        
    Returns:
        Diccionario con información del PDF generado o None si falla
    """
    try:
        # Generar título basado en el nivel de riesgo (sin emojis para compatibilidad con headers HTTP)
        title = f"Informe de Evaluacion de Riesgo de Diabetes - Riesgo {risk_level.upper()}"
        
        # Generar descripción
        age = session.variables.get('Age_Years', 'N/A')
        bmi = session.variables.get('BMI', 'N/A')
        bmi_str = f"{bmi:.1f}" if isinstance(bmi, (int, float)) else str(bmi)
        
        description = f"Evaluacion de riesgo de diabetes. Nivel: {risk_level.upper()} ({risk_score:.1%}). Edad: {age} anos, IMC: {bmi_str}. Generado por MediNutrIA."
        
        # Convertir risk_score (0-1) a porcentaje (0-100)
        percentage = risk_score * 100
        
        # Preparar el payload para la API
        pdf_payload = {
            "html_content": html_content,
            "title": title,
            "description": description,
            "percentage": percentage
        }
        
        # Obtener URL del servicio PDF desde variable de entorno
        pdf_service_url = os.getenv('PDF_SERVICE_URL', 'http://localhost:8000')
        pdf_api_url = f"{pdf_service_url}/api/pdf/create"
        
        logger.info(f"📄 Generando PDF usando servicio: {pdf_api_url}")
        
        # Llamar a la API local de creación de PDF
        async with httpx.AsyncClient() as client:
            response = await client.post(
                pdf_api_url,
                json=pdf_payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                pdf_data = response.json()
                logger.info(f"PDF generado exitosamente: {pdf_data.get('pdf_id')}")
                return pdf_data
            else:
                logger.error(f"Error al generar PDF: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        logger.error(f"Error generando PDF: {e}")
        return None


async def complete_assessment(session) -> CoachResponse:
    """Completa la evaluación y genera predicción con recomendaciones."""
    
    try:
        # Calcular BMI
        calculate_bmi(session)
        
        # Realizar predicción
        risk_score, risk_level = predict_diabetes_risk(session.variables)
        
        # Guardar en sesión
        session.risk_prediction = risk_score
        session.risk_level = risk_level
        
        # Obtener interpretación personalizada
        interpretation = get_risk_interpretation(risk_score, risk_level, session.variables)
        
        # Generar recomendaciones específicas usando el agente
        context_for_agent = f"""
El usuario ha completado una evaluación de riesgo de diabetes con los siguientes resultados:

- **Nivel de riesgo:** {risk_level.upper()}
- **Probabilidad:** {risk_score:.1%}
- **IMC:** {session.variables.get('BMI', 'N/A'):.1f}
- **Edad:** {session.variables.get('Age_Years', 'N/A')} años
- **Antecedentes familiares:** {"Sí" if session.variables.get('Family_History_Diabetes') == 1 else "No"}
- **Actividad física:** {session.variables.get('Total_MET_Score', 0):.0f} MET-min/semana

Genera recomendaciones específicas y motivadoras basadas en su perfil.
"""
        
        # Usar el agente para generar recomendaciones adicionales
        agent_recommendations = ""
        if run_agent_flow:
            try:
                agent_out = run_agent_flow(context_for_agent)
                agent_recommendations = agent_out.get('final', '')
            except Exception as e:
                logger.error(f"Error en agente: {e}")
        
        # Combinar interpretación + recomendaciones del agente
        final_response = f"""
## 📊 Resultados de tu Evaluación

{interpretation}


{agent_recommendations if agent_recommendations else ""}


---

💙 **Recuerda:** Esta evaluación es orientativa y está basada en datos estadísticos. **No reemplaza una consulta médica profesional**. Te recomendamos consultar con tu médico para una evaluación completa y personalizada.

🎯 **Próximo paso:** Guarda estos resultados y compártelos con tu médico en tu próxima consulta.
"""
        
        final_html = render_markdown_to_safe_html(final_response)
        
        # Generar PDF con el informe
        pdf_data = await generate_assessment_pdf(
            html_content=final_html,
            risk_level=risk_level,
            risk_score=risk_score,
            session=session
        )
        
        # Agregar enlace del PDF a la respuesta
        if pdf_data:
            pdf_link_html = f"""
<div style="margin-top: 30px; padding: 20px; background-color: #f0f9ff; border-left: 4px solid #3b82f6; border-radius: 8px;">
    <h3 style="margin: 0 0 10px 0; color: #1e40af;">📄 Tu Informe está Listo</h3>
    <p style="margin: 0 0 15px 0;">Hemos generado un PDF completo con tu evaluación y recomendaciones personalizadas.</p>
    <div>
        <a href="{pdf_data.get('download_url')}" 
           style="display: inline-block; padding: 12px 24px; background-color: #3b82f6; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
            ⬇️ Descargar Informe en PDF
        </a>
    </div>
</div>
"""
            final_html += pdf_link_html
        
        return CoachResponse(
            risk=risk_level,
            retrieved_count=0,
            draft="",
            final=final_html,
            session_id=session.session_id,
            is_question=False,
            question_progress=f"{len(VARIABLE_QUESTIONS)}/{len(VARIABLE_QUESTIONS)}",
            details={
                "risk_score": risk_score,
                "variables": session.variables,
                "bmi": session.variables.get("BMI"),
                "pdf_data": pdf_data
            }
        )
        
    except Exception as e:
        logger.exception("Error completando evaluación")
        error_html = render_markdown_to_safe_html(f"""
### ❌ Error en la Evaluación

Lo siento, ocurrió un error al procesar tu evaluación: {str(e)}

Por favor, intenta nuevamente o consulta con el administrador del sistema.
""")
        return CoachResponse(
            risk="error",
            retrieved_count=0,
            draft="",
            final=error_html,
            session_id=session.session_id,
            is_question=False
        )


async def handle_normal_conversation(request: CoachRequest) -> CoachResponse:
    """Maneja la conversación normal con el agente (sin evaluación)."""
    if run_agent_flow is None:
        raise HTTPException(status_code=500, detail="run_agent_flow no disponible")
    
    try:
        out = run_agent_flow(request.query)
        final_html = render_markdown_to_safe_html(out.get('final', ''))
        draft_text = out.get('draft', '') or ''
        
        return CoachResponse(
            risk=out.get('risk', 'medio'),
            retrieved_count=len(out.get('retrieved', [])),
            draft=draft_text,
            final=final_html,
            details={k: v for k, v in out.items() if k not in ('draft', 'final')}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def render_markdown_to_safe_html(text: str) -> str:
    """Convierte Markdown a HTML seguro."""
    if not text:
        return ''
    # Si disponemos de markdown, convertir; si no, usar texto tal cual.
    md_html = markdown.markdown(text, extensions=['extra']) if markdown else html.escape(text)
    # Si disponemos de bleach, sanitizar y linkify; si no, devolver HTML escapado
    if bleach:
        allowed_tags = set(bleach.sanitizer.ALLOWED_TAGS) | { 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'p', 'ul', 'ol', 'li', 'strong', 'em', 'del', 'code', 'pre', 'blockquote' }
        allowed_attrs = { 'a': ['href', 'title', 'rel'], 'img': ['src', 'alt'], 'code': ['class'] }
        cleaned = bleach.clean(md_html, tags=allowed_tags, attributes=allowed_attrs)
        cleaned = bleach.linkify(cleaned)
        return cleaned
    return md_html
