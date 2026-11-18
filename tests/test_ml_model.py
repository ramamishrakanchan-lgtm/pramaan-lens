import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.analysis import FEATURE_NAMES, numeric_features
from backend.ml_model import feature_vector, predict_risk


class AnalysisFeatureTests(unittest.TestCase):
    def test_numeric_features_include_requested_signals(self):
        flags = [
            {"check": "Metadata"},
            {"check": "Message order"},
            {"check": "Date logic"},
            {"check": "Date logic"},
        ]
        words = [{"confidence": 80.0}, {"confidence": 60.0}]

        features = numeric_features(flags, words, 0.125, 9)

        self.assertEqual(features["metadata_flag_count"], 1)
        self.assertEqual(features["message_order_flag_count"], 1)
        self.assertEqual(features["date_logic_flag_count"], 2)
        self.assertEqual(features["date_anomaly_count"], 2)
        self.assertEqual(features["order_anomaly_count"], 1)
        self.assertEqual(features["ocr_confidence"], 70.0)
        self.assertEqual(features["edited_region_score"], 0.125)
        self.assertEqual(features["hash_distance"], 9.0)
        self.assertEqual(set(features), set(FEATURE_NAMES))

    def test_feature_vector_uses_stable_feature_order(self):
        features = {name: index for index, name in enumerate(FEATURE_NAMES)}

        self.assertEqual(feature_vector(features), list(range(len(FEATURE_NAMES))))


class OptionalModelTests(unittest.TestCase):
    def test_missing_model_returns_no_prediction(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing.joblib"
            self.assertIsNone(predict_risk({}, missing_path))

    def test_prediction_returns_class_and_probability(self):
        class FakeModel:
            classes_ = ["HIGH", "LOW"]

            @staticmethod
            def predict_proba(rows):
                return [[0.2, 0.8]]

        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "model.joblib"
            model_path.touch()
            fake_joblib = SimpleNamespace(load=lambda path: FakeModel())
            with patch.dict(sys.modules, {"joblib": fake_joblib}):
                result = predict_risk({name: 0 for name in FEATURE_NAMES}, model_path)

        self.assertEqual(result, {"label": "LOW", "confidence": 0.8})


if __name__ == "__main__":
    unittest.main()
