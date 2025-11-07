from pathlib import Path
import logging
from typing import List
import numpy as np

try:
    from src import utils
except ImportError:
    import utils

logger = logging.getLogger(__name__)

def retrieve_relevant(query: str, top_k: int = 5) -> List[dict]:
    """Recupera los `top_k` fragmentos más similares desde el índice (kb/db/index.npz).

    Devuelve lista de metadatas con clave adicional `score` (cosine similarity).
    """
    index_path = Path(__file__).parent.parent / 'kb' / 'db' / 'index.npz'
    if not index_path.exists():
        logger.info('No se encontró índice en %s', index_path)
        return []
    emb_arr, metadatas = utils.load_index(index_path)
    if emb_arr is None or not metadatas:
        return []

    q_emb = utils.embed_texts([query])[0]
    emb_matrix = np.array(emb_arr)
    qv = np.array(q_emb)

    def cos(a, b):
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        return float(np.dot(a, b) / denom) if denom != 0 else 0.0

    scores = [cos(qv, emb_matrix[i]) for i in range(len(emb_matrix))]
    idxs = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    results = []
    for i in idxs:
        m = dict(metadatas[i])
        m['score'] = scores[i]
        results.append(m)
    return results
