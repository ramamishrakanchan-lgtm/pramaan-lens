"""Train the experimental classifier with generated synthetic screenshots only."""
import argparse
import io
import random
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

import imagehash
import joblib
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from backend import custody
from backend.analysis import FEATURE_NAMES, analyze

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLES_DIR = ROOT / "assets" / "samples"
DEFAULT_MODEL_PATH = ROOT / "models" / "model.joblib"
CLAIMED_DATE = date(2026, 11, 18)
SCENARIOS = {
    "clean": "LOW",
    "order_anomaly": "MEDIUM",
    "metadata_tag": "MEDIUM",
    "date_mismatch": "HIGH",
    "prior_match": "HIGH",
}
SAMPLE_SCENARIOS = ("clean", "order_anomaly", "metadata_tag", "date_mismatch")


def render_synthetic_screenshot(scenario, seed):
    """Create one obviously synthetic chat-style screenshot as PNG bytes."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown synthetic scenario: {scenario}")

    rng = random.Random(seed)
    image = Image.new("RGB", (960, 680), "#F1F4F2")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=24)
    small_font = ImageFont.load_default(size=18)

    draw.rectangle((0, 0, 960, 92), fill="#176B55")
    draw.ellipse((26, 20, 76, 70), fill="#D9E8E1")
    draw.text((96, 25), f"Sample Chat {seed % 17 + 1}", font=font, fill="white")
    draw.text((96, 56), "SYNTHETIC DEMO - NOT A REAL CONVERSATION", font=small_font, fill="#DDF1E8")
    shown_date = "19/11/2026" if scenario == "date_mismatch" else "18/11/2026"
    draw.rounded_rectangle((350, 112, 610, 150), radius=16, fill="#DDE7E2")
    draw.text((400, 122), shown_date, font=small_font, fill="#35443C")

    first_time, second_time = ("10:17 AM", "10:12 AM") if scenario == "order_anomaly" else ("10:12 AM", "10:17 AM")
    bubble_color = rng.choice(("#FFFFFF", "#F8FCFA", "#FDFBF6"))
    draw.rounded_rectangle((70, 190, 620, 315), radius=22, fill=bubble_color)
    draw.text((100, 220), f"Hello, this is sample {seed % 31 + 1}.", font=font, fill="#26332C")
    draw.text((100, 272), first_time, font=small_font, fill="#69766E")
    draw.rounded_rectangle((270, 350, 890, 475), radius=22, fill="#D8F3E4")
    draw.text((300, 380), f"Reply for synthetic case {seed % 43 + 1}.", font=font, fill="#26332C")
    draw.text((300, 432), second_time, font=small_font, fill="#69766E")
    draw.text((70, 555), "Generated for offline software testing and demonstration.", font=small_font, fill="#68736D")
    draw.text((70, 590), "No real people, messages, or evidence are depicted.", font=small_font, fill="#68736D")

    output = io.BytesIO()
    if scenario == "metadata_tag":
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("Software", "Canva")
        image.save(output, format="PNG", pnginfo=metadata)
    else:
        image.save(output, format="PNG")
    return output.getvalue()


def generate_sample_screenshots(samples_dir=DEFAULT_SAMPLES_DIR):
    samples_dir = Path(samples_dir)
    samples_dir.mkdir(parents=True, exist_ok=True)
    for index, scenario in enumerate(SAMPLE_SCENARIOS):
        image_path = samples_dir / f"{scenario}.png"
        image_path.write_bytes(render_synthetic_screenshot(scenario, seed=100 + index))
    return samples_dir


def build_synthetic_dataset(examples_per_scenario=20):
    if examples_per_scenario < 4:
        raise ValueError("Use at least four examples per scenario for a held-out split.")

    rows, labels = [], []
    with tempfile.TemporaryDirectory(prefix="pramaanlens-synthetic-") as temp_dir:
        for scenario_index, (scenario, label) in enumerate(SCENARIOS.items()):
            for example_index in range(examples_per_scenario):
                seed = 1000 * scenario_index + example_index
                raw = render_synthetic_screenshot(scenario, seed)
                database_path = Path(temp_dir) / f"{scenario_index}-{example_index}.sqlite"
                with patch.object(custody, "DB", database_path):
                    if scenario == "prior_match":
                        with Image.open(io.BytesIO(raw)) as image:
                            prior_hash = str(imagehash.phash(image))
                        custody.register(f"synthetic-prior-{seed}", "0" * 64, prior_hash, "synthetic-prior.png")
                    result = analyze(raw, f"synthetic-{scenario}-{seed}.png", CLAIMED_DATE)
                rows.append([result["features"][name] for name in FEATURE_NAMES])
                labels.append(label)
    return rows, labels


def train_model(examples_per_scenario=20, model_path=DEFAULT_MODEL_PATH, samples_dir=DEFAULT_SAMPLES_DIR):
    generate_sample_screenshots(samples_dir)
    rows, labels = build_synthetic_dataset(examples_per_scenario)
    x_train, x_test, y_train, y_test = train_test_split(
        rows, labels, test_size=0.25, random_state=42, stratify=labels
    )
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)

    precision = precision_score(y_test, predictions, average="macro", zero_division=0)
    recall = recall_score(y_test, predictions, average="macro", zero_division=0)
    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)

    print("Synthetic-only evaluation; scores do not estimate real-world accuracy.")
    print(f"Held-out synthetic examples: {len(y_test)}")
    print(f"Macro precision: {precision:.3f}")
    print(f"Macro recall:    {recall:.3f}")
    print(f"Saved synthetic-data model to: {model_path}")
    return model, {"precision": precision, "recall": recall}


def main():
    """Run synthetic-only training and evaluation from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples-per-scenario", type=int, default=20)
    parser.add_argument("--samples-dir", type=Path, default=DEFAULT_SAMPLES_DIR)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    args = parser.parse_args()
    train_model(args.examples_per_scenario, args.model_path, args.samples_dir)


if __name__ == "__main__":
    main()
