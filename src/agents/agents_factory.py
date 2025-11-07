from pathlib import Path
import os
import sys
import json
import logging
from typing import List, Optional, Callable
from functools import lru_cache

import numpy as np

# Intento robusto de importar `utils` desde `src` o como módulo plano
try:
    from src import utils
    from src.agents.openai_utils import get_call_model
    from src.retrieval import retrieve_relevant
except ImportError:
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from src import utils
        from src.agents.openai_utils import get_call_model
        from src.retrieval import retrieve_relevant
    except ImportError:
        import utils  # type: ignore
        from openai_utils import get_call_model # type: ignore
        from retrieval import retrieve_relevant # type: ignore


logger = logging.getLogger(__name__)
if not logger.handlers:
    # configuración mínima si no existe una configuración de logging global
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


# Directorio con instrucciones de agentes (markdown)
KB_AGENTS_DIR = Path(__file__).resolve().parent.parent / 'kb' / 'agents'

# Cache del índice en memoria para evitar lecturas repetidas desde disco
_INDEX_CACHE: Optional[tuple] = None  # (emb_arr, metadatas)


def _load_index_cached(index_path: Path):
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        emb_arr, metadatas = utils.load_index(index_path)
        _INDEX_CACHE = (emb_arr, metadatas)
    return _INDEX_CACHE


@lru_cache(maxsize=256)
def _embed_query_cached(query: str):
    try:
        return utils.embed_texts([query])[0]
    except Exception:
        logger.exception('Fallo al generar embedding para query')
        # devolver vector neutro para no romper la pipeline
        return [0.0]


def _read_agent_instructions(name: str) -> str:
    path = KB_AGENTS_DIR / f"{name}.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding='utf-8')
    # eliminar fences de código para evitar confundir prompts
    lines = []
    skip = False
    for ln in text.splitlines():
        if ln.strip().startswith('```'):
            skip = not skip
            continue
        if not skip:
            lines.append(ln)
    return '\n'.join(lines)


def run_risk_selector(user_input: str, call_model: Callable, model_default: str) -> str:
    risk_prompt = _read_agent_instructions('risk_selector_agent') + f"\n\nUser query:\n{user_input}\n\nPor favor responde solo con 'bajo', 'medio' o 'alto'."
    try:
        risk_out = call_model(risk_prompt, model=model_default, max_tokens=10)
        if risk_out:
            risk = (risk_out or '').strip().lower().split()[0]
            if risk not in ('bajo', 'medio', 'alto'):
                risk = 'medio'
        else:
            risk = 'medio'
    except Exception:
        logger.exception('Risk selector failed, defaulting to medio')
        risk = 'medio'
    return risk

def run_retrieval(user_input: str) -> tuple[list[dict], str]:
    # Parametrizar top_k y tamaño de snippet por ENV para ajustes rápidos
    top_k_env = int(os.getenv('RETRIEVAL_TOP_K', '3'))  # Reducido de 5 a 3 para mayor velocidad
    snippet_chars = int(os.getenv('RETRIEVAL_SNIPPET_CHARS', '350'))  # Reducido de 500 a 350

    # retrieve_relevant internamente puede ser una función que lee desde disco;
    # si existe una versión local cargada (src.retrieval) la usamos, si no, usamos
    # utils.load_index pero desde memoria (cache).
    try:
        # intentar usar la función importada retrieve_relevant (si fue sobrescrita)
        retrieved = retrieve_relevant(user_input, top_k=top_k_env)
    except Exception:
        # fallback: cargar índice en memoria y calcular similitud localmente
        index_path = Path(__file__).parent.parent / 'kb' / 'db' / 'index.npz'
        if not index_path.exists():
            logger.info('No se encontró índice en %s', index_path)
            return [], ''
        emb_arr, metadatas = _load_index_cached(index_path)
        if emb_arr is None or not metadatas:
            return [], ''
        q_emb = _embed_query_cached(user_input)
        emb_matrix = np.array(emb_arr)
        qv = np.array(q_emb)

        def cos(a, b):
            denom = (np.linalg.norm(a) * np.linalg.norm(b))
            return float(np.dot(a, b) / denom) if denom != 0 else 0.0

        scores = [cos(qv, emb_matrix[i]) for i in range(len(emb_matrix))]
        idxs = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k_env]
        retrieved = []
        for i in idxs:
            m = dict(metadatas[i])
            if 'text' in m and isinstance(m['text'], str):
                m['text'] = m['text'][:snippet_chars]
            m['score'] = scores[i]
            retrieved.append(m)

    # Construir contexto reducido para ahorrar tokens y latencia
    context = '\n\n---\n\n'.join([f"Source: {r.get('source')}\nScore: {r.get('score'):.4f}\nText:\n{r.get('text')}" for r in retrieved])
    return retrieved, context

RISK_TEMPERATURE_MAP = {
    "bajo": 0.0,
    "medio": 0.5,
    "alto": 1.0,
}

def run_draft_generator(user_input: str, context: str, risk: str, call_model: Callable, model_default: str, temperature: float) -> str:
    """Genera el borrador de respuesta pasando el nivel de riesgo al agente de retrieval."""
    # Incluir el nivel de riesgo en el prompt para que el agente adapte su respuesta
    risk_info = f"\n\n**NIVEL DE RIESGO DETECTADO: {risk.upper()}**\nAdapta tu respuesta según las instrucciones para riesgo {risk}."
    retrieval_prompt = _read_agent_instructions('retrieval') + risk_info + f"\n\nConsulta:\n{user_input}\n\nContexto recuperado:\n{context}"
    draft = ''
    try:
        draft = (call_model(retrieval_prompt, model=model_default, temperature=temperature, max_tokens=800) or '').strip()
    except Exception:
        logger.exception('Draft generation failed; trying fallback prompt')
        try:
            fb_prompt = f"Responde brevemente a la consulta del usuario:\n{user_input}\n\nProvee recomendaciones prácticas y pasos a seguir."
            draft = (call_model(fb_prompt, model=model_default, temperature=temperature, max_tokens=800) or '').strip()
        except Exception:
            logger.exception('Fallback draft failed')
            draft = ''
    return draft

def run_formatter(draft: str, user_input: str, call_model: Callable, model_default: str, temperature: float) -> str:
    formatter_prompt = _read_agent_instructions('formatter') + f"\n\nBorrador:\n{draft}\n\nPor favor formatea según las reglas. NO incluyas las palabras 'Borrador:' o 'Revisión:' en tu respuesta."
    final = ''
    try:
        final = (call_model(formatter_prompt, model=model_default, temperature=temperature, max_tokens=1000) or '').strip()
    except Exception:
        logger.exception('Formatter failed; trying simple response prompt')
        try:
            simple_prompt = f"Por favor, responde de forma clara y breve a esta consulta:\n{user_input}\n\nIncluye recomendaciones prácticas y próximas acciones cuando corresponda."
            final = (call_model(simple_prompt, model=model_default, temperature=temperature, max_tokens=1000) or '').strip()
        except Exception:
            logger.exception('Fallback final failed')
            final = ''

    if not final:
        final = 'Lo siento — no pude generar una respuesta en este momento. Intenta de nuevo más tarde.'
    
    final = final.replace('<p>', '').replace('</p>', '').replace('<br>', '\n').strip()
    return final

def run_agent_flow(user_input: str, run_risk_model: Optional[Callable] = None) -> dict:
    """Orquesta el flujo de agentes y devuelve un dict con `risk`, `retrieved`, `draft`, `final`.

    - run_risk_model: función opcional para ejecutar un modelo de riesgo (si aplica).
    """
    call_model = get_call_model()
    model_default = os.getenv('LLM_MODEL', 'gpt-4')

    # Modelos configurables: para reducir latencia podemos usar un modelo más barato
    # para la generación del borrador. Ajusta con la variable DRAFT_MODEL.
    draft_model = os.getenv('DRAFT_MODEL', model_default)
    formatter_model = os.getenv('FORMATTER_MODEL', model_default)

    # Detectar si es un saludo simple o pregunta trivial (sin contenido médico)
    user_lower = user_input.lower().strip()
    simple_greetings = ['hola', 'hi', 'hello', 'buenos días', 'buenas tardes', 'buenas noches', 
                        'hey', 'saludos', 'qué tal', 'cómo estás', 'como estas']
    
    is_simple_greeting = any(greeting == user_lower or user_lower.startswith(greeting + ' ') or user_lower.startswith(greeting + ',') 
                             for greeting in simple_greetings)
    
    if is_simple_greeting and len(user_input.split()) <= 3:
        # Respuesta directa para saludos simples, sin flujo completo
        return {
            'risk': 'bajo',
            'retrieved': [],
            'draft': '',
            'final': '¡Hola! 👋 Soy MediNutrIA, tu asistente de salud y nutrición. ¿En qué puedo ayudarte hoy? Puedes preguntarme sobre alimentación, ejercicio, condiciones de salud o cualquier tema relacionado con tu bienestar.'
        }

    risk = run_risk_selector(user_input, call_model, model_default)
    temperature = RISK_TEMPERATURE_MAP.get(risk, 0.5)

    retrieved, context = run_retrieval(user_input)
    # Pasar el nivel de riesgo al draft generator para que adapte la respuesta
    draft = run_draft_generator(user_input, context, risk, call_model, draft_model, temperature)
    final = run_formatter(draft, user_input, call_model, formatter_model, temperature)
    
    # Limpiar marcadores de debug que puedan haber quedado
    final = final.replace('Borrador:', '').replace('Revisión:', '').strip()
    final = final.replace('<p>', '').replace('</p>', '').replace('<br>', '\n').strip()

    # Añadir disclaimer médico solo si la respuesta contiene contenido de salud sustancial
    # (evitar disclaimer en saludos o respuestas muy cortas)
    if len(final) > 100:  # Solo si la respuesta tiene contenido sustancial
        disclaimer = "\n\n\n\n💙Recuerda: Esta información es solo para fines educativos y está basada en una recopilación de datos confiables. Sin embargo, **no reemplaza una consulta médica profesional**. Siempre es importante que consultes con tu médico o un profesional de la salud calificado para recibir un diagnóstico y tratamiento personalizado. ¡Tu salud es lo más importante! 💙"
        final = final + disclaimer

    return {
        'risk': risk,
        'retrieved': retrieved,
        'draft': draft,
        'final': final,
    }


if __name__ == '__main__':
    # Demo interactivo
    q = input('Ingresa consulta: ')
    out = run_agent_flow(q)
    logger.info('\n--- RESULT ---\n')
    logger.info(json.dumps({'risk': out['risk'], 'retrieved_count': len(out['retrieved'])}, ensure_ascii=False, indent=2))
    logger.info('\nFinal Response:\n')
    logger.info(out['final'])
