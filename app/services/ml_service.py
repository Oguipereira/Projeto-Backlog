from pathlib import Path
import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MIN_SAMPLES = 10  # mínimo de incidentes para treinar


def _text(inc) -> str:
    return f"{inc.title or ''} {inc.description or ''}".strip().lower()


def _build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(max_features=800, ngram_range=(1, 2), min_df=1)),
        ("clf",   LogisticRegression(max_iter=1000, random_state=42, C=1.0)),
    ])


def train_all(incidents: list) -> dict:
    """Treina classificadores de prioridade, sistema e tipo. Retorna status."""
    texts = [_text(i) for i in incidents]
    if len(texts) < MIN_SAMPLES:
        return {"status": "insufficient_data", "count": len(texts), "needed": MIN_SAMPLES}

    results = {"status": "ok", "count": len(texts)}

    # Prioridade
    priorities = [i.priority for i in incidents]
    pipe = _build_pipeline()
    pipe.fit(texts, priorities)
    joblib.dump(pipe, MODELS_DIR / "priority.pkl")
    results["priority"] = "ok"

    # Sistema
    sys_pairs = [(t, i.system.name) for t, i in zip(texts, incidents) if i.system]
    if len(sys_pairs) >= MIN_SAMPLES:
        sys_texts, sys_labels = zip(*sys_pairs)
        pipe = _build_pipeline()
        pipe.fit(sys_texts, sys_labels)
        joblib.dump(pipe, MODELS_DIR / "system.pkl")
        results["system"] = "ok"

    # Tipo
    type_pairs = [(t, i.incident_type.name) for t, i in zip(texts, incidents) if i.incident_type]
    if len(type_pairs) >= MIN_SAMPLES:
        type_texts, type_labels = zip(*type_pairs)
        pipe = _build_pipeline()
        pipe.fit(type_texts, type_labels)
        joblib.dump(pipe, MODELS_DIR / "type.pkl")
        results["type"] = "ok"

    return results


_MODEL_CACHE: dict = {}


def _load_model(fname: str):
    """Carrega modelo do disco uma vez e mantém em memória."""
    path = MODELS_DIR / fname
    if not path.exists():
        return None
    cached = _MODEL_CACHE.get(fname)
    if cached is None or path.stat().st_mtime != _MODEL_CACHE.get(f"{fname}__mtime"):
        _MODEL_CACHE[fname] = joblib.load(path)
        _MODEL_CACHE[f"{fname}__mtime"] = path.stat().st_mtime
    return _MODEL_CACHE[fname]


def suggest_classification(title: str, description: str) -> dict:
    """Prevê prioridade, sistema e tipo com base no texto. Retorna dict com confiança."""
    text = f"{title or ''} {description or ''}".strip().lower()
    result = {}

    for key, fname in [("priority", "priority.pkl"), ("system", "system.pkl"), ("incident_type", "type.pkl")]:
        pipe = _load_model(fname)
        if pipe is None:
            continue
        pred  = pipe.predict([text])[0]
        proba = pipe.predict_proba([text])[0].max()
        result[key] = str(pred)
        result[f"{key}_confidence"] = int(round(proba * 100))

    return result


def invalidate_cache():
    """Limpa o cache de modelos — chamar após retreinamento."""
    _MODEL_CACHE.clear()


def models_status() -> dict:
    """Retorna status de cada modelo (treinado ou não)."""
    return {
        key: (MODELS_DIR / fname).exists()
        for key, fname in [
            ("priority", "priority.pkl"),
            ("system",   "system.pkl"),
            ("type",     "type.pkl"),
        ]
    }
