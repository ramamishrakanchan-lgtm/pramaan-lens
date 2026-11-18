"""Optional experimental risk classifier trained only on synthetic screenshots."""
from pathlib import Path

from .analysis import FEATURE_NAMES

MODEL_PATH = Path(__file__).resolve().parent.parent / "model.joblib"


def feature_vector(features):
    """Return analysis signals in the stable order used by the trained model."""
    return [float(features[name]) for name in FEATURE_NAMES]


def predict_risk(features, model_path=MODEL_PATH):
    """Return a predicted risk label and class probability, or None without a model."""
    model_path = Path(model_path)
    if not model_path.is_file():
        return None

    import joblib

    model = joblib.load(model_path)
    probabilities = model.predict_proba([feature_vector(features)])[0]
    class_index = max(range(len(probabilities)), key=probabilities.__getitem__)
    label = str(model.classes_[class_index])
    if label not in {"HIGH", "MEDIUM", "LOW"}:
        raise ValueError(f"Unsupported risk label in ML model: {label}")
    return {"label": label, "confidence": float(probabilities[class_index])}
