from typing import List
from pathlib import Path
import os
import json
import numpy as np
try:
    # Cargar variables del .env del proyecto (si existe)
    from dotenv import load_dotenv
    # Buscar .env en la raíz del proyecto (dos niveles arriba desde src/)
    project_root = Path(__file__).parent.parent
    dotenv_path = project_root / '.env'
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
    else:
        # fallback: intentar carga por defecto (buscar en cwd y padres)
        load_dotenv()
except Exception:
    # Si python-dotenv no está instalado, no fallamos; el código seguirá
    # usando las variables de entorno ya exportadas en el sistema.
    pass


def chunk_text(text: str, max_chars: int = 1000) -> List[str]:
    """Divide el texto en fragmentos de aproximadamente `max_chars` caracteres.

    Estrategia simple: partir por líneas/párrafos y agrupar hasta el límite.
    """
    parts = []
    current = []
    current_len = 0
    # dividir por párrafos
    for para in text.split('\n\n'):
        p = para.strip()
        if not p:
            continue
        if current_len + len(p) + 1 <= max_chars:
            current.append(p)
            current_len += len(p) + 1
        else:
            if current:
                parts.append('\n\n'.join(current))
            # if single paragraph larger than max_chars, split it
            if len(p) > max_chars:
                # split by sentences of approx max_chars
                for i in range(0, len(p), max_chars):
                    parts.append(p[i:i+max_chars])
                current = []
                current_len = 0
            else:
                current = [p]
                current_len = len(p) + 1
    if current:
        parts.append('\n\n'.join(current))
    return parts


def embed_texts(texts: List[str], model: str = None):
    """Generar embeddings para una lista de textos.

    - Si está presente la variable de entorno OPENAI_API_KEY, usa la API de OpenAI
      y el modelo indicado por EMBEDDING_MODEL (por defecto 'text-embedding-3-small').
    - Si no hay API key, cae en un fallback local usando sentence-transformers
      (requiere instalación de `sentence-transformers`).

    Devuelve una lista de vectores (listas de floats).
    """
    openai_key = os.getenv('OPENAI_API_KEY')
    model = model or os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
    if openai_key:
        try:
            import openai
        except Exception:
            raise RuntimeError("Falta la dependencia 'openai'. Instálala con: pip install openai")
        openai.api_key = openai_key
        # Llamar en batches para no exceder límites de tamaño
        batch_size = 100
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            resp = openai.Embedding.create(model=model, input=batch)
            for item in resp['data']:
                embeddings.append(item['embedding'])
        return embeddings
    else:
        # Fallback local
        try:
            from sentence_transformers import SentenceTransformer
        except Exception:
            raise RuntimeError(
                "No se encontró OPENAI_API_KEY ni la dependencia 'sentence-transformers'. Instálala con: pip install sentence-transformers"
            )
        model_local = SentenceTransformer('all-MiniLM-L6-v2')
        emb_arr = model_local.encode(texts, show_progress_bar=False)
        return emb_arr.tolist()


def save_index(emb_arr: np.ndarray, metadatas: List[dict], index_path: Path):
    """Guardar el índice en formato .npz con embeddings y metadatos.

    - embeddings: array numpy (n_fragments, dim)
    - metadatas: lista de dicts con metadata por fragmento
    - index_path: Path al archivo .npz destino
    """
    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    # Guardar embeddings y metadatas (serializadas)
    meta_json = json.dumps(metadatas, ensure_ascii=False)
    np.savez_compressed(str(index_path), embeddings=emb_arr, metadatas=meta_json)
    print(f"Índice guardado en {index_path}")


def extract_text_from_pdf(path: Path) -> List[str]:
    """Extrae texto de un PDF y devuelve una lista de páginas (cada elemento es el texto de una página).

    Usa PyPDF2 como dependencia ligera. Si una página está vacía, se devuelve cadena vacía.
    """
    try:
        from PyPDF2 import PdfReader
    except Exception:
        raise RuntimeError("Falta la dependencia 'PyPDF2'. Instálala con: pip install PyPDF2")
    reader = PdfReader(str(path))
    pages = []
    for p in reader.pages:
        try:
            txt = p.extract_text() or ""
        except Exception:
            txt = ""
        pages.append(txt)
    return pages
