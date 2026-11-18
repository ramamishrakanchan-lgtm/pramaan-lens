import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from backend.train_model import (
    SAMPLE_SCENARIOS,
    generate_sample_screenshots,
    render_synthetic_screenshot,
    train_model,
)


class SyntheticTrainingTests(unittest.TestCase):
    def test_synthetic_screenshot_is_readable_png(self):
        image_bytes = render_synthetic_screenshot("clean", seed=1)
        with Image.open(io.BytesIO(image_bytes)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (960, 680))

    def test_generate_samples_creates_each_synthetic_scenario(self):
        with tempfile.TemporaryDirectory() as directory:
            samples_dir = generate_sample_screenshots(directory)

            self.assertEqual(
                {path.stem for path in samples_dir.glob("*.png")},
                set(SAMPLE_SCENARIOS),
            )

    def test_training_saves_a_model_from_a_synthetic_split(self):
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "model.joblib"
            samples_dir = Path(directory) / "samples"

            _, scores = train_model(4, model_path, samples_dir)

            self.assertTrue(model_path.is_file())
            self.assertGreaterEqual(scores["precision"], 0.0)
            self.assertLessEqual(scores["precision"], 1.0)
            self.assertGreaterEqual(scores["recall"], 0.0)
            self.assertLessEqual(scores["recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
