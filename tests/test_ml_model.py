import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from backend.analysis import FEATURE_NAMES, _ela_analysis, annotate, numeric_features
from backend.ml_model import feature_vector, predict_risk


class AnalysisFeatureTests(unittest.TestCase):
    def test_numeric_features_include_requested_signals(self):
        flags = [
            {"check": "Metadata", "level": "LOW"},
            {"check": "Message order", "level": "MEDIUM"},
            {"check": "Date logic", "level": "HIGH"},
            {"check": "Date logic", "level": "HIGH"},
        ]
        words = [{"confidence": 80.0}, {"confidence": 60.0}]

        features = numeric_features(flags, words, 0.125, 9)

        self.assertEqual(features["metadata_flag_count"], 1)
        self.assertEqual(features["message_order_flag_count"], 1)
        self.assertEqual(features["date_logic_flag_count"], 2)
        self.assertEqual(features["date_anomaly_count"], 2)
        self.assertEqual(features["order_anomaly_count"], 1)
        self.assertEqual(features["high_flag_count"], 2)
        self.assertEqual(features["medium_flag_count"], 1)
        self.assertEqual(features["low_flag_count"], 1)
        self.assertEqual(features["ocr_confidence"], 70.0)
        self.assertEqual(features["edited_region_score"], 0.125)
        self.assertEqual(features["hash_distance"], 9.0)
        self.assertEqual(set(features), set(FEATURE_NAMES))

    def test_feature_vector_uses_stable_feature_order(self):
        features = {name: index for index, name in enumerate(FEATURE_NAMES)}

        self.assertEqual(feature_vector(features), list(range(len(FEATURE_NAMES))))

    def test_annotate_keeps_region_interiors_visible(self):
        source = Image.new("RGB", (120, 80), "white")
        flags = [{
            "level": "LOW",
            "region": None,
            "regions": [(20, 25, 30, 30), (70, 25, 30, 30)],
        }]

        marked = annotate(source, flags)

        self.assertEqual(marked.size, source.size)
        self.assertEqual(marked.getpixel((30, 40)), (255, 255, 255))
        self.assertEqual(marked.getpixel((20, 40)), (16, 185, 129))

    def test_marker_size_only_changes_the_annotation_weight(self):
        source = Image.new("RGB", (120, 80), "white")
        flags = [{"level": "LOW", "region": (20, 25, 30, 30), "regions": []}]

        standard = annotate(source, flags)
        larger = annotate(source, flags, marker_scale=3)

        self.assertEqual(standard.getpixel((23, 40)), (255, 255, 255))
        self.assertEqual(larger.getpixel((23, 40)), (16, 185, 129))
        self.assertEqual(source.getpixel((23, 40)), (255, 255, 255))

    def test_ela_regions_are_one_grouped_flag(self):
        image = Image.new("RGB", (100, 100), "white")
        with (
            patch("backend.analysis.cv2.findContours", return_value=([1, 2], None)),
            patch("backend.analysis.cv2.contourArea", return_value=100),
            patch("backend.analysis.cv2.boundingRect", side_effect=[(10, 10, 20, 20), (50, 50, 20, 20)]),
        ):
            flags, _ = _ela_analysis(image)

        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["regions"], [(10, 10, 20, 20), (50, 50, 20, 20)])
        self.assertIn("2 regions", flags[0]["observation"])


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
