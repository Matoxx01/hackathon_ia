import os
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

def _call_model_modern(prompt: str, model: str, temperature: float, max_tokens: Optional[int] = None) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    try:
        kwargs = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception:
            logger.debug('client.chat.completions.create failed without temperature, retrying with temperature', exc_info=True)
            kwargs["temperature"] = temperature
            resp = client.chat.completions.create(**kwargs)

        choices = getattr(resp, 'choices', None)
        if choices:
            c = choices[0]
            if isinstance(c, dict):
                return c.get('message', {}).get('content', '')
            else:
                return c.message.content
    except Exception:
        logger.exception('client.chat.completions.create failed')
    return ''

def _call_model_classic(prompt: str, model: str, temperature: float, max_tokens: Optional[int] = None) -> str:
    import openai
    openai.api_key = os.getenv('OPENAI_API_KEY')
    kwargs = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    
    try:
        resp = openai.ChatCompletion.create(**kwargs)
    except Exception:
        logger.debug('openai.ChatCompletion.create failed without temperature, retrying with temperature', exc_info=True)
        kwargs["temperature"] = temperature
        resp = openai.ChatCompletion.create(**kwargs)
    return resp['choices'][0]['message']['content']

def get_call_model() -> Callable[[str, Optional[str], float, Optional[int]], str]:
    """Construye y devuelve una función `call_model(prompt, model, temperature, max_tokens)`.

    La función detecta la librería `openai` instalada y utiliza la interfaz
    disponible. Lanza RuntimeError si no se puede invocar la API o si falta la clave.
    """

    def call_model(prompt: str, model: Optional[str] = None, temperature: float = 0.0, max_tokens: Optional[int] = None) -> str:
        model = model or os.getenv('LLM_MODEL', 'gpt-4')
        key = os.getenv('OPENAI_API_KEY')
        logger.debug("call_model: model=%s prompt_len=%d max_tokens=%s", model, len(prompt), max_tokens)
        if not key:
            raise RuntimeError('OPENAI_API_KEY no configurada - no es posible invocar el LLM')

        try:
            from openai import OpenAI
            return _call_model_modern(prompt, model, temperature, max_tokens)
        except ImportError:
            try:
                return _call_model_classic(prompt, model, temperature, max_tokens)
            except Exception:
                logger.exception('Fallback openai.ChatCompletion failed')

        raise RuntimeError('No fue posible invocar la API de OpenAI con la configuración actual')

    return call_model
