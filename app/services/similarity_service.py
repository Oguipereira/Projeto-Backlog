"""
Busca por incidentes similares usando TF-IDF + similaridade de cosseno.

Interface projetada para troca futura por embeddings (Claude API)
sem alterar os chamadores.
"""
from typing import List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import Incident
from app.utils.calculations import format_duration


def _text(inc: Incident) -> str:
    return f"{inc.title or ''} {inc.description or ''} {inc.root_cause or ''}".strip().lower()


def find_similar(
    title: str,
    description: str,
    candidates: List[Incident],
    top_k: int = 5,
    min_score: float = 0.10,
) -> List[dict]:
    """
    Retorna os `top_k` incidentes mais similares ao texto de entrada.

    Cada resultado traz:
      - incident_id, title, system, priority, status
      - duration_formatted, root_cause, resolution_notes
      - similarity_score (0.0 – 1.0)
    """
    if not candidates:
        return []

    query   = f"{title or ''} {description or ''}".strip().lower()
    corpus  = [_text(c) for c in candidates]
    docs    = [query] + corpus

    try:
        vec    = TfidfVectorizer(max_features=1000, ngram_range=(1, 2), min_df=1)
        matrix = vec.fit_transform(docs)
    except ValueError:
        return []

    scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

    ranked = sorted(
        zip(scores, candidates),
        key=lambda x: x[0],
        reverse=True,
    )

    results = []
    for score, inc in ranked[:top_k]:
        if score < min_score:
            break
        results.append({
            "incident_id":        inc.incident_id,
            "title":              inc.title,
            "system":             inc.system.name if inc.system else "-",
            "priority":           inc.priority,
            "status":             inc.status,
            "duration_formatted": format_duration(inc.duration_minutes or 0),
            "root_cause":         inc.root_cause or "",
            "resolution_notes":   inc.resolution_notes or "",
            "similarity_score":   round(float(score), 4),
            "similarity_pct":     int(round(float(score) * 100)),
        })

    return results
