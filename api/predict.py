"""
Módulo para cargar y ejecutar el modelo de predicción de diabetes.
"""
import pickle
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

# Ruta al modelo
MODEL_PATH = Path(__file__).parent.parent / "model" / "modelo"

# Variables esperadas por el modelo (en orden)
EXPECTED_FEATURES = [
    "Gender",
    "Age_Years",
    "Ethnicity",
    "Weight_kg",
    "Height_cm",
    "BMI",
    "Diabetes_Diagnosis",
    "Prediabetes_Diagnosis",
    "Perceived_Diabetes_Risk",
    "Overweight_Diagnosis",
    "Congestive_Heart_Failure",
    "Coronary_Artery_Disease",
    "Thyroid_Problem",
    "Jaundice_Diagnosis",
    "Family_History_Diabetes",
    "Total_MET_Score"
]

# Valores por defecto para variables no recopiladas
DEFAULT_VALUES = {
    "Ethnicity": 3,  # Valor neutro
    "Perceived_Diabetes_Risk": 2,  # Riesgo medio percibido
    "Jaundice_Diagnosis": 2,  # No diagnosticado
}


def load_model():
    """Carga el modelo desde disco."""
    try:
        with open(MODEL_PATH, 'rb') as f:
            model = pickle.load(f)
        logger.info(f"Modelo cargado exitosamente desde {MODEL_PATH}")
        return model
    except FileNotFoundError:
        logger.error(f"Modelo no encontrado en {MODEL_PATH}")
        raise
    except Exception as e:
        logger.error(f"Error cargando el modelo: {e}")
        raise


# Cache del modelo en memoria
_MODEL_CACHE = None


def get_model():
    """Obtiene el modelo (cargado en memoria si ya existe)."""
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        _MODEL_CACHE = load_model()
    return _MODEL_CACHE


def prepare_features(variables: Dict[str, Any]) -> np.ndarray:
    """
    Prepara las features para el modelo a partir de las variables recopiladas.
    
    Args:
        variables: Diccionario con las variables recopiladas
        
    Returns:
        Array numpy con las features en el orden esperado
    """
    features = []
    
    for feature_name in EXPECTED_FEATURES:
        if feature_name in variables:
            features.append(variables[feature_name])
        elif feature_name in DEFAULT_VALUES:
            features.append(DEFAULT_VALUES[feature_name])
        else:
            # Si falta una variable crítica, usar un valor neutro
            logger.warning(f"Variable faltante: {feature_name}, usando 0")
            features.append(0)
    
    return np.array([features])


def predict_diabetes_risk(variables: Dict[str, Any]) -> Tuple[float, str]:
    """
    Realiza la predicción de riesgo de diabetes.
    
    Args:
        variables: Diccionario con las variables del usuario
        
    Returns:
        Tuple con (probabilidad_riesgo, nivel_riesgo)
        - probabilidad_riesgo: float entre 0 y 1
        - nivel_riesgo: str ("bajo", "medio", "alto")
    """
    try:
        # Obtener el modelo
        model = get_model()
        
        # Preparar features
        X = prepare_features(variables)
        
        # Realizar predicción
        # El modelo puede retornar probabilidades o clases
        if hasattr(model, 'predict_proba'):
            # Si tiene predict_proba, obtener la probabilidad de la clase positiva
            proba = model.predict_proba(X)[0]
            # Asumiendo que la clase 1 es diabetes
            risk_score = proba[1] if len(proba) > 1 else proba[0]
        else:
            # Si solo tiene predict, obtener la predicción binaria
            prediction = model.predict(X)[0]
            risk_score = float(prediction)
        
        # Clasificar el nivel de riesgo
        if risk_score < 0.3:
            risk_level = "bajo"
        elif risk_score < 0.6:
            risk_level = "medio"
        else:
            risk_level = "alto"
        
        logger.info(f"Predicción completada: score={risk_score:.3f}, nivel={risk_level}")
        
        return risk_score, risk_level
        
    except Exception as e:
        logger.error(f"Error en predicción: {e}")
        raise


def get_risk_interpretation(risk_score: float, risk_level: str, variables: Dict[str, Any]) -> str:
    """
    Genera una interpretación del riesgo basada en el score y las variables.
    
    Args:
        risk_score: Probabilidad de riesgo (0-1)
        risk_level: Nivel de riesgo ("bajo", "medio", "alto")
        variables: Variables del usuario
        
    Returns:
        Interpretación textual del riesgo
    """
    interpretations = {
        "bajo": f"""
### 🟢 Riesgo Bajo de Diabetes (Probabilidad: {risk_score:.1%})

¡Buenas noticias! Tu perfil actual indica un **riesgo bajo** de desarrollar diabetes. Sin embargo, la prevención es clave.

**Factores positivos en tu perfil:**
- Mantén tus hábitos saludables actuales
- Continúa con actividad física regular
- Sigue con una alimentación balanceada

**Recomendaciones:**
- Realiza chequeos anuales de glucosa
- Mantén un peso saludable
- Continúa con al menos 150 minutos de ejercicio semanal
""",
        "medio": f"""
### 🟡 Riesgo Moderado de Diabetes (Probabilidad: {risk_score:.1%})

Tu perfil indica un **riesgo moderado** de desarrollar diabetes. Es importante tomar medidas preventivas ahora.

**Aspectos a considerar:**
- Algunos factores de riesgo están presentes
- La intervención temprana puede reducir significativamente el riesgo
- Cambios en el estilo de vida pueden hacer una gran diferencia

**Recomendaciones importantes:**
- 📋 Consulta con un médico para evaluación completa
- 🏃 Incrementa tu actividad física a 200+ minutos semanales
- 🥗 Adopta una dieta baja en azúcares y rica en fibra
- ⚖️ Si tienes sobrepeso, una pérdida del 5-10% puede reducir el riesgo significativamente
- 🩺 Realiza chequeos de glucosa cada 6 meses
""",
        "alto": f"""
### 🔴 Riesgo Alto de Diabetes (Probabilidad: {risk_score:.1%})

**⚠️ IMPORTANTE:** Tu perfil indica un **riesgo alto** de desarrollar diabetes. Se requiere atención médica prioritaria.

**Situación actual:**
- Múltiples factores de riesgo están presentes
- La intervención médica es urgente y necesaria
- El manejo adecuado puede prevenir o retrasar la diabetes

**Acciones URGENTES recomendadas:**

1. 🚨 **Consulta médica INMEDIATA**
   - Solicita evaluación completa de glucosa (HbA1c, glucosa en ayunas)
   - Discute un plan de prevención personalizado
   - Considera evaluación con endocrinólogo

2. 🏃 **Actividad física (ESENCIAL)**
   - Mínimo 150 minutos semanales de ejercicio moderado
   - Combina ejercicio aeróbico y de resistencia
   - Empieza gradualmente con caminatas diarias

3. 🥗 **Cambios alimenticios (PRIORITARIOS)**
   - Elimina bebidas azucaradas y alimentos procesados
   - Aumenta consumo de vegetales, proteínas magras y fibra
   - Controla porciones y horarios de comidas
   - Considera asesoría con nutricionista

4. ⚖️ **Control de peso**
   - Si tienes sobrepeso, pérdida del 7-10% es crucial
   - Establece metas realistas y graduales
   - Monitorea tu progreso semanalmente

5. 🩺 **Monitoreo constante**
   - Chequeos de glucosa mensuales
   - Seguimiento de presión arterial
   - Control de peso semanal
"""
    }
    
    base_interpretation = interpretations.get(risk_level, "")
    
    # Agregar factores de riesgo específicos identificados
    risk_factors = []
    
    if variables.get("BMI", 0) > 30:
        risk_factors.append("- **Obesidad** (IMC > 30): Factor de riesgo importante")
    elif variables.get("BMI", 0) > 25:
        risk_factors.append("- **Sobrepeso** (IMC 25-30): Reducir peso ayudará significativamente")
    
    if variables.get("Family_History_Diabetes") == 1:
        risk_factors.append("- **Antecedentes familiares**: Mayor vigilancia necesaria")
    
    if variables.get("Prediabetes_Diagnosis") == 1:
        risk_factors.append("- **Prediabetes diagnosticada**: Intervención urgente puede prevenir diabetes")
    
    if variables.get("Total_MET_Score", 0) < 600:  # < 150 min/semana aprox
        risk_factors.append("- **Actividad física insuficiente**: Incrementar ejercicio es prioritario")
    
    if variables.get("Age_Years", 0) > 45:
        risk_factors.append("- **Edad > 45 años**: Mayor riesgo, monitoreo regular importante")
    
    if risk_factors:
        base_interpretation += "\n\n**Factores de riesgo identificados en tu perfil:**\n" + "\n".join(risk_factors)
    
    return base_interpretation
