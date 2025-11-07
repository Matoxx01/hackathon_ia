"""
Sistema de sesiones para recopilar variables del modelo de predicción de diabetes.
"""
from typing import Dict, Optional, List, Any
from datetime import datetime
from pydantic import BaseModel
import uuid


class PredictionSession(BaseModel):
    """Sesión de recopilación de datos para predicción."""
    session_id: str
    started_at: str
    variables: Dict[str, Any] = {}
    current_question_index: int = 0
    completed: bool = False
    risk_prediction: Optional[float] = None
    risk_level: Optional[str] = None


# Definición de variables y preguntas en orden lógico
VARIABLE_QUESTIONS = [
    {
        "variable": "Gender",
        "question": "Para comenzar, ¿cuál es tu sexo biológico?",
        "options": ["Hombre", "Mujer"],
        "map": {"hombre": 1, "mujer": 2},
        "type": "choice"
    },
    {
        "variable": "Age_Years",
        "question": "¿Cuántos años tienes?",
        "type": "number",
        "min": 1,
        "max": 120,
        "unit": "años"
    },
    {
        "variable": "Weight_kg",
        "question": "¿Cuál es tu peso actual?",
        "type": "number",
        "min": 20,
        "max": 300,
        "unit": "kg"
    },
    {
        "variable": "Height_cm",
        "question": "¿Cuál es tu altura?",
        "type": "number",
        "min": 100,
        "max": 250,
        "unit": "cm"
    },
    {
        "variable": "Diabetes_Diagnosis",
        "question": "¿Has sido diagnosticado/a con diabetes por un médico?",
        "options": ["Sí", "No"],
        "map": {"sí": 1, "si": 1, "no": 2},
        "type": "choice"
    },
    {
        "variable": "Prediabetes_Diagnosis",
        "question": "¿Te han diagnosticado prediabetes o niveles altos de glucosa?",
        "options": ["Sí", "No"],
        "map": {"sí": 1, "si": 1, "no": 2},
        "type": "choice"
    },
    {
        "variable": "Family_History_Diabetes",
        "question": "¿Algún familiar directo (padres, hermanos) tiene diabetes?",
        "options": ["Sí", "No"],
        "map": {"sí": 1, "si": 1, "no": 2},
        "type": "choice"
    },
    {
        "variable": "Overweight_Diagnosis",
        "question": "¿Has sido diagnosticado/a con sobrepeso por un médico?",
        "options": ["Sí", "No"],
        "map": {"sí": 1, "si": 1, "no": 2},
        "type": "choice"
    },
    {
        "variable": "Congestive_Heart_Failure",
        "question": "¿Has sido diagnosticado/a con insuficiencia cardíaca congestiva?",
        "options": ["Sí", "No"],
        "map": {"sí": 1, "si": 1, "no": 2},
        "type": "choice"
    },
    {
        "variable": "Coronary_Artery_Disease",
        "question": "¿Has sido diagnosticado/a con enfermedad coronaria?",
        "options": ["Sí", "No"],
        "map": {"sí": 1, "si": 1, "no": 2},
        "type": "choice"
    },
    {
        "variable": "Thyroid_Problem",
        "question": "¿Tienes algún problema de tiroides diagnosticado?",
        "options": ["Sí", "No"],
        "map": {"sí": 1, "si": 1, "no": 2},
        "type": "choice"
    },
    {
        "variable": "Total_MET_Score",
        "question": "En una semana típica, ¿cuántos minutos dedicas a actividad física moderada o intensa? (caminar rápido, correr, gym, deportes)",
        "type": "number",
        "min": 0,
        "max": 5000,
        "unit": "minutos/semana",
        "transform": lambda x: x * 4.0  # Conversión aproximada a MET-score
    }
]


# Almacenamiento en memoria de sesiones (en producción usar Redis/DB)
_SESSIONS: Dict[str, PredictionSession] = {}


def create_session() -> PredictionSession:
    """Crea una nueva sesión de predicción."""
    session = PredictionSession(
        session_id=str(uuid.uuid4()),
        started_at=datetime.utcnow().isoformat()
    )
    _SESSIONS[session.session_id] = session
    return session


def get_session(session_id: str) -> Optional[PredictionSession]:
    """Obtiene una sesión existente."""
    return _SESSIONS.get(session_id)


def get_or_create_session(session_id: Optional[str] = None) -> PredictionSession:
    """Obtiene una sesión existente o crea una nueva."""
    if session_id and session_id in _SESSIONS:
        return _SESSIONS[session_id]
    return create_session()


def get_next_question(session: PredictionSession) -> Optional[Dict[str, Any]]:
    """Obtiene la siguiente pregunta para la sesión."""
    if session.current_question_index >= len(VARIABLE_QUESTIONS):
        session.completed = True
        return None
    return VARIABLE_QUESTIONS[session.current_question_index]


def process_answer(session: PredictionSession, answer: str) -> Dict[str, Any]:
    """
    Procesa la respuesta del usuario y actualiza la sesión.
    
    Returns:
        Dict con: success (bool), message (str), next_question (dict o None)
    """
    if session.completed:
        return {
            "success": False,
            "message": "La sesión ya ha sido completada.",
            "next_question": None
        }
    
    current_q = VARIABLE_QUESTIONS[session.current_question_index]
    variable = current_q["variable"]
    q_type = current_q["type"]
    
    # Validar y procesar respuesta
    try:
        if q_type == "choice":
            answer_lower = answer.strip().lower()
            if "map" in current_q:
                mapped_value = current_q["map"].get(answer_lower)
                if mapped_value is None:
                    return {
                        "success": False,
                        "message": f"Por favor responde con una de las opciones: {', '.join(current_q['options'])}",
                        "next_question": current_q
                    }
                session.variables[variable] = mapped_value
            else:
                session.variables[variable] = answer.strip()
                
        elif q_type == "number":
            # Extraer número de la respuesta
            import re
            numbers = re.findall(r'\d+\.?\d*', answer)
            if not numbers:
                return {
                    "success": False,
                    "message": f"Por favor proporciona un número válido (entre {current_q.get('min', 0)} y {current_q.get('max', 1000)}).",
                    "next_question": current_q
                }
            
            value = float(numbers[0])
            
            # Validar rango
            if "min" in current_q and value < current_q["min"]:
                return {
                    "success": False,
                    "message": f"El valor debe ser al menos {current_q['min']}.",
                    "next_question": current_q
                }
            if "max" in current_q and value > current_q["max"]:
                return {
                    "success": False,
                    "message": f"El valor debe ser máximo {current_q['max']}.",
                    "next_question": current_q
                }
            
            # Aplicar transformación si existe
            if "transform" in current_q:
                value = current_q["transform"](value)
            
            session.variables[variable] = value
        
        # Avanzar a la siguiente pregunta
        session.current_question_index += 1
        next_q = get_next_question(session)
        
        return {
            "success": True,
            "message": "Respuesta registrada correctamente.",
            "next_question": next_q
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error procesando la respuesta: {str(e)}",
            "next_question": current_q
        }


def calculate_bmi(session: PredictionSession) -> None:
    """Calcula el BMI si hay peso y altura disponibles."""
    if "Weight_kg" in session.variables and "Height_cm" in session.variables:
        weight = session.variables["Weight_kg"]
        height_m = session.variables["Height_cm"] / 100.0
        session.variables["BMI"] = weight / (height_m ** 2)


def get_missing_variables(session: PredictionSession) -> List[str]:
    """Obtiene las variables que aún faltan por recopilar."""
    required = [q["variable"] for q in VARIABLE_QUESTIONS]
    return [v for v in required if v not in session.variables]


def is_session_complete(session: PredictionSession) -> bool:
    """Verifica si la sesión tiene todas las variables necesarias."""
    return session.completed and len(get_missing_variables(session)) == 0
