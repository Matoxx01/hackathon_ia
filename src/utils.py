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
    # Si python-dotenv no está instalado, intentar parsear manualmente el .env
    try:
        dotenv_path = Path(__file__).parent.parent / '.env'
        if dotenv_path.exists():
            with open(dotenv_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and not os.getenv(k):
                        os.environ[k] = v
    except Exception:
        # Si todo falla, no hacemos nada; el proceso puede depender de variables ya definidas
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


def _embed_openai(texts: List[str], model: str) -> List[List[float]]:
    try:
        import openai
    except ImportError:
        raise RuntimeError("Falta la dependencia 'openai'. Instálala con: pip install openai")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        batch_size = 100
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            resp = client.embeddings.create(model=model, input=batch)
            for item in getattr(resp, 'data', []):
                if isinstance(item, dict):
                    embeddings.append(item.get('embedding'))
                else:
                    embeddings.append(getattr(item, 'embedding', None))
        return embeddings
    except Exception:
        openai.api_key = os.getenv('OPENAI_API_KEY')
        batch_size = 100
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            resp = openai.Embedding.create(model=model, input=batch)
            for item in resp['data']:
                embeddings.append(item['embedding'])
        return embeddings

def _embed_sentence_transformer(texts: List[str]) -> List[List[float]]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "No se encontró OPENAI_API_KEY ni la dependencia 'sentence-transformers'. Instálala con: pip install sentence-transformers"
        )
    model_local = SentenceTransformer('all-MiniLM-L6-v2')
    emb_arr = model_local.encode(texts, show_progress_bar=False)
    return emb_arr.tolist()

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
        return _embed_openai(texts, model)
    else:
        return _embed_sentence_transformer(texts)


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


def load_index(index_path: Path):
    """Cargar embeddings y metadatas desde un .npz guardado por save_index.

    Devuelve (embeddings: np.ndarray, metadatas: list)
    """
    index_path = Path(index_path)
    if not index_path.exists():
        raise FileNotFoundError(f"No se encontró índice en {index_path}")
    data = np.load(str(index_path), allow_pickle=True)
    emb = data.get('embeddings')
    meta_raw = data.get('metadatas')
    metadatas = []
    if meta_raw is not None:
        try:
            if isinstance(meta_raw, (bytes, bytearray)):
                meta_str = meta_raw.decode('utf-8')
            else:
                meta_str = str(meta_raw.tolist()) if hasattr(meta_raw, 'tolist') else str(meta_raw)
            metadatas = json.loads(meta_str)
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                metadatas = eval(meta_raw)
            except Exception:
                metadatas = []
    return emb, metadatas


def save_index_with_json(emb_arr: np.ndarray, metadatas: List[dict], index_path: Path):
    """Versión más robusta de save_index: guarda .npz con embeddings y un archivo .meta.json con la metadata.

    Esto hace más fácil inspeccionar y depurar la metadata fuera de numpy.
    """
    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    # Guardar solo embeddings en .npz
    np.savez_compressed(str(index_path), embeddings=emb_arr)
    # Guardar metadata como JSON separado
    meta_path = index_path.with_suffix(index_path.suffix + '.meta.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadatas, f, ensure_ascii=False, indent=2)
    print(f"Índice guardado en {index_path} y metadata en {meta_path}")


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
