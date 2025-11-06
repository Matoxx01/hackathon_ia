from typing import List
from pathlib import Path
import os
import json
import numpy as np


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


def embed_texts(texts: List[str]):
    """Generar embeddings para una lista de textos usando sentence-transformers.

    Requiere la instalación de `sentence-transformers`.
    Devuelve una lista de vectores (listas de floats).
    """
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        raise RuntimeError(
            "Falta la dependencia 'sentence-transformers'. Instálala con: pip install sentence-transformers"
        )
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


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
