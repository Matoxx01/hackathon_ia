from pathlib import Path
import json
from utils import chunk_text, embed_texts, save_index, extract_text_from_pdf
import numpy as np

KB_DIR = Path(__file__).parent.parent / 'kb'
INDEX_PATH = KB_DIR / 'db' / 'index.npz'


def load_documents(kb_dir: Path, papers_dir: Path = None):
    """Cargar únicamente archivos markdown bajo `kb/papers/` para indexar.

    El archivo `role.md` se excluye intencionalmente porque contiene las
    instrucciones/guardrails del agente y no debe formar parte del índice de
    embeddings.
    """
    docs = []
    if not papers_dir.exists():
        return docs
    # MarkDown files
    for p in papers_dir.rglob('*.md'):
        # saltar archivos ocultos o con nombre index
        if p.name.startswith('index'):
            continue
        text = p.read_text(encoding='utf-8')
        # derivar un título simple: primera línea no vacía o el nombre del archivo
        title = None
        for line in text.splitlines():
            s = line.strip()
            if s:
                title = s
                break
        if not title:
            title = p.stem
        docs.append({'source': str(p.relative_to(kb_dir)), 'text': text, 'title': title})
    # PDF files: extraer por páginas y tratar cada página como un "documento" breve
    for p in papers_dir.rglob('*.pdf'):
        try:
            pages = extract_text_from_pdf(p)
        except Exception as e:
            print(f"Advertencia: no se pudo leer PDF {p}: {e}")
            continue
        for i, page_text in enumerate(pages):
            title = f"{p.stem} - page {i+1}"
            source = str(p.relative_to(kb_dir)) + f"::page_{i+1}"
            docs.append({'source': source, 'text': page_text, 'title': title})
    return docs


def build_index(kb_dir: Path, papers_dir: Path, index_path: Path):
    """Construir y guardar el índice de embeddings a partir de los documentos.

    Lee los documentos, los divide en fragmentos, genera embeddings y guarda
    el índice junto con los metadatos.
    """
    docs = load_documents(kb_dir, papers_dir)
    chunks = []
    metadatas = []
    for d in docs:
        parts = chunk_text(d['text'], max_chars=1000)
        for i, p in enumerate(parts):
            chunks.append(p)
            metadatas.append({
                'source': d['source'],
                'title': d.get('title'),
                'chunk_id': i,
                'text': p,
                'text_preview': p[:200]
            })
    print(f"Generando embeddings para {len(chunks)} fragmentos...")
    embeddings = embed_texts(chunks)
    emb_arr = np.array(embeddings)
    save_index(emb_arr, metadatas, index_path)
    print(f"Índice guardado en {index_path}")


if __name__ == '__main__':
    build_index(KB_DIR, KB_DIR / 'data_rag', INDEX_PATH)