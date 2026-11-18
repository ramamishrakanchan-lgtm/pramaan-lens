"""Rule-based, offline analysis. Every flag points to an image region or a metadata field.
No generative LLM, and no genuine/fake verdict: only HIGH / MEDIUM / LOW risk flags."""
import datetime as dt
import io
import re

import cv2
import imagehash
import numpy as np
from PIL import ExifTags, Image, ImageColor, ImageDraw, ImageFont
from . import custody

EDITORS = ("photoshop", "gimp", "canva", "snapseed", "picsart", "pixlr", "lightroom", "paint.net", "figma", "fotor")
RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
COLORS = {"HIGH": "#B3342F", "MEDIUM": "#C98A1B", "LOW": "#4F7A64"}
DATE_RE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})")
REL_RE = re.compile(r"today|yesterday")
CHECK_FEATURES = {
    "metadata_flag_count": "Metadata",
    "ocr_flag_count": "OCR",
    "message_order_flag_count": "Message order",
    "date_logic_flag_count": "Date logic",
    "ui_consistency_flag_count": "UI consistency",
    "reuse_detection_flag_count": "Reuse detection",
}
FEATURE_NAMES = (
    *CHECK_FEATURES,
    "high_flag_count",
    "medium_flag_count",
    "low_flag_count",
    "ocr_confidence",
    "edited_region_score",
    "date_anomaly_count",
    "order_anomaly_count",
    "hash_distance",
)


def _flag(check, obs, level, action, region=None, field=None, regions=None):
    return dict(check=check, observation=obs, level=level, action=action, region=region, field=field,
                regions=regions or [])


def _hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


# 1. Metadata -----------------------------------------------------------
def metadata(img):
    """Return image metadata and metadata-related risk flags."""
    info, flags = {}, []
    ex = img.getexif()
    for k, v in ex.items():
        info[ExifTags.TAGS.get(k, str(k))] = str(v)
    try:
        for k, v in ex.get_ifd(0x8769).items():
            info[ExifTags.TAGS.get(k, str(k))] = str(v)
    except Exception:
        pass
    for k, v in img.info.items():
        if isinstance(v, str):
            info[f"png:{k}"] = v[:200]
    sw = (info.get("Software", "") + " " + info.get("png:Software", "")).lower()
    hit = next((e for e in EDITORS if e in sw), None)
    if hit:
        flags.append(_flag("Metadata", f"Editing-software tag detected ({hit})", "MEDIUM", "Examine original file", field="Software"))
    if not info:
        flags.append(_flag("Metadata", "No EXIF/XMP found. Forwarding strips metadata, so this is neutral", "LOW", "Request the original file if available", field="EXIF"))
    return info, flags


def capture_time(info):
    """Parse an EXIF capture timestamp when one is available."""
    for k in ("DateTimeOriginal", "DateTime"):
        try:
            return dt.datetime.strptime(info[k][:19], "%Y:%m:%d %H:%M:%S")
        except (KeyError, ValueError):
            continue
    return None


# 2. OCR ----------------------------------------------------------------
def ocr_words(img):
    """Extract recognized words, bounding boxes, and confidence values."""
    import pytesseract
    d = pytesseract.image_to_data(img.convert("RGB"), output_type=pytesseract.Output.DICT)
    words = []
    for i, text in enumerate(d["text"]):
        text = text.strip()
        if text:
            try:
                confidence = float(d["conf"][i])
            except (KeyError, TypeError, ValueError):
                confidence = 0.0
            words.append(dict(t=text, box=(d["left"][i], d["top"][i], d["width"][i], d["height"][i]),
                              confidence=max(0.0, min(100.0, confidence))))
    return words


def _times(words):
    out = []
    for i, w in enumerate(words):
        m = re.fullmatch(r"(\d{1,2}):(\d{2})([ap]m)?", w["t"], re.I)
        if not m or int(m[1]) > 23 or int(m[2]) > 59:
            continue
        h, mi = int(m[1]), int(m[2])
        suf = (m[3] or (words[i + 1]["t"] if i + 1 < len(words) else "")).lower()
        if suf in ("am", "pm"):
            h = h % 12 + (12 if suf == "pm" else 0)
        out.append((w, h * 60 + mi))
    return out


def _union(a, b):
    x, y = min(a[0], b[0]), min(a[1], b[1])
    return (x, y, max(a[0] + a[2], b[0] + b[2]) - x, max(a[1] + a[3], b[1] + b[3]) - y)


# 3. Message order + date logic -------------------------------------------
def order_flags(words):
    """Flag decreasing message times within a visible date segment."""
    seps = [w["box"][1] for w in words if REL_RE.fullmatch(w["t"].strip(",:").lower()) or DATE_RE.fullmatch(w["t"])]
    segs = {}
    for w, m in sorted(_times(words), key=lambda x: x[0]["box"][1]):
        segs.setdefault(sum(y < w["box"][1] for y in seps), []).append((w, m))
    flags = []
    for items in segs.values():  # compare only inside one date segment
        for a, b in zip(items, items[1:]):
            if b[1] < a[1]:
                flags.append(_flag("Message order", f"{_hhmm(a[1])} appears before {_hhmm(b[1])} in the same day",
                                   "MEDIUM", "Inspect original conversation", region=_union(a[0]["box"], b[0]["box"])))
                break
    return flags


def date_flags(words, capture, claimed):
    """Compare visible dates with the claimed date and available capture time."""
    flags = []
    for w in words:
        word = w["t"].strip(",:").lower()
        if REL_RE.fullmatch(word) and claimed:
            if capture is None:
                flags.append(_flag("Date logic", f"'{word.title()}' label cannot be anchored: no capture time in metadata",
                                   "LOW", "Verify original chat/device", region=w["box"]))
                continue
            expected = capture.date() - dt.timedelta(days=1 if word == "yesterday" else 0)
            if expected != claimed:
                flags.append(_flag("Date logic", f"'{word.title()}' conflicts with claimed date ({claimed}) and capture time ({capture:%Y-%m-%d %H:%M})",
                                   "HIGH", "Verify original chat/device", region=w["box"]))
        m = DATE_RE.fullmatch(w["t"])
        if m and claimed:
            try:
                shown = dt.date(int(m[3]), int(m[2]), int(m[1]))
            except ValueError:
                continue
            if shown != claimed:
                flags.append(_flag("Date logic", f"Date separator {shown} differs from claimed date {claimed}",
                                   "HIGH" if shown > claimed else "MEDIUM", "Verify original chat/device", region=w["box"]))
    return flags


# 4. UI / edited-region check (error-level analysis, low confidence by design)
def _ela_analysis(img):
    rgb = img.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=90)
    re_img = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    diff = np.abs(np.asarray(rgb, dtype=np.int16) - np.asarray(re_img, dtype=np.int16)).sum(2).astype(np.float32)
    diff = cv2.GaussianBlur(diff, (0, 0), 3)
    mask = ((diff > diff.mean() + 4 * diff.std()).astype(np.uint8)) * 255
    mask = cv2.dilate(mask, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = mask.shape
    boxes = sorted((cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > 0.002 * h * w), key=lambda b: -b[2] * b[3])[:3]
    regions = [tuple(int(v) for v in box) for box in boxes]
    flags = []
    if regions:
        region_word = "region" if len(regions) == 1 else "regions"
        flags.append(_flag(
            "UI consistency",
            f"Compression differs in {len(regions)} {region_word}. ELA is noisy on screenshots.",
            "LOW",
            "Inspect the highlighted regions visually",
            regions=regions,
        ))
    return flags, float(np.count_nonzero(mask) / mask.size)


def ela_flags(img):
    """Return low-confidence compression-difference flags for an image."""
    return _ela_analysis(img)[0]


# 5. Reuse detection --------------------------------------------------------
def _reuse_analysis(ph, case_id):
    distances = [(cid, ph - imagehash.hex_to_hash(hx)) for cid, hx in custody.previous(case_id)]
    nearest_distance = min((distance for _, distance in distances), default=64)
    flags = [_flag("Reuse detection", f"Perceptually similar to earlier case {cid} (distance {distance})",
                   "HIGH", "Compare with the earlier case file", field=f"phash:{cid}")
             for cid, distance in distances if distance <= 6]
    return flags, nearest_distance


def reuse_flags(ph, case_id):
    """Return flags for perceptually similar previously registered cases."""
    return _reuse_analysis(ph, case_id)[0]


def numeric_features(flags, words, edited_region_score, hash_distance):
    """Build the stable numeric feature mapping consumed by the ML assist."""
    counts = {
        feature: sum(flag["check"] == check for flag in flags)
        for feature, check in CHECK_FEATURES.items()
    }
    counts.update({
        f"{level.lower()}_flag_count": sum(flag["level"] == level for flag in flags)
        for level in RANK
    })
    confidence_values = [float(word.get("confidence", 0.0)) for word in words]
    ocr_confidence = (sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0
    counts.update({
        "ocr_confidence": ocr_confidence,
        "edited_region_score": float(edited_region_score),
        "date_anomaly_count": counts["date_logic_flag_count"],
        "order_anomaly_count": counts["message_order_flag_count"],
        "hash_distance": float(hash_distance),
    })
    return counts


# Pipeline ----------------------------------------------------------------
def analyze(raw: bytes, filename: str, claimed=None):
    """Run offline checks, record custody events, and return findings and features."""
    digest = custody.sha256(raw)
    case_id = digest[:12]
    custody.log(case_id, "UPLOAD_SEALED", f"{filename} sha256={digest}")
    img = Image.open(io.BytesIO(raw))
    img.load()
    info, flags = metadata(img)
    words = []
    try:
        words = ocr_words(img)
    except Exception as e:  # Tesseract missing or failed: say so, never guess
        flags.append(_flag("OCR", f"OCR unavailable ({type(e).__name__}); text checks skipped", "LOW", "Install Tesseract and re-run", field="OCR"))
    flags += order_flags(words) + date_flags(words, capture_time(info), claimed)
    edited_flags, edited_region_score = _ela_analysis(img)
    flags += edited_flags
    ph = imagehash.phash(img)
    reuse, hash_distance = _reuse_analysis(ph, case_id)
    flags += reuse
    features = numeric_features(flags, words, edited_region_score, hash_distance)
    custody.register(case_id, digest, str(ph), filename)
    custody.log(case_id, "ANALYSED", f"{len(flags)} flags, ocr_words={len(words)}")
    flags.sort(key=lambda f: -RANK[f["level"]])
    return dict(case_id=case_id, sha256=digest, filename=filename, flags=flags, metadata=info, image=img,
                top=flags[0]["level"] if flags else "LOW", features=features)


# 6. Annotated image (clear boxes + labels) -----------------------------------
BOX = {"HIGH": "#E5322D", "MEDIUM": "#F59E0B", "LOW": "#10B981"}


def _font(size):
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate(img, flags, marker_scale=1.0):
    """Draw non-destructive severity outlines and labels on a copy of the image."""
    base = img.convert("RGBA")
    if not 0.5 <= marker_scale <= 3.0:
        raise ValueError("marker_scale must be between 0.5 and 3.0")
    scale = max(1.0, max(base.size) / 1000) * marker_scale
    lw = max(2, round(2 * scale))
    fs = max(12, round(14 * scale))
    font = _font(fs)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ordered_flags = sorted(flags, key=lambda f: RANK[f["level"]])
    all_regions = [
        (x, y, x + w, y + h)
        for flag in ordered_flags
        for x, y, w, h in (flag.get("regions") or ([flag["region"]] if flag.get("region") else []))
    ]
    label_rects = []
    for f in ordered_flags:
        regions = f.get("regions") or ([f["region"]] if f.get("region") else [])
        for index, region in enumerate(regions, start=1):
            x, y, w, h = region
            x2, y2 = x + w, y + h
            rgb = ImageColor.getrgb(BOX[f["level"]])
            d.rectangle([x, y, x2, y2], outline=rgb + (255,), width=lw)
            badge_background, badge_text = {
                "HIGH": ("#FCE9E7", "#9D2823"),
                "MEDIUM": ("#FFF2D6", "#805400"),
                "LOW": ("#E7F3EB", "#28613C"),
            }[f["level"]]
            label = f["level"]
            if len(regions) > 1:
                label += f" {index}/{len(regions)}"
            l, t, r, b = d.textbbox((0, 0), label, font=font)
            tw, th = r - l, b - t
            pad = max(4, fs // 3)
            badge_w, badge_h = tw + 2 * pad, th + 2 * pad
            candidates = (
                (x, y - badge_h - lw),
                (x, y2 + lw),
                (x2 + lw, y),
                (x - badge_w - lw, y),
            )
            position = None
            for candidate_x, candidate_y in candidates:
                candidate_rect = (candidate_x, candidate_y, candidate_x + badge_w, candidate_y + badge_h)
                inside_image = (
                    candidate_x >= 0 and candidate_y >= 0
                    and candidate_rect[2] <= base.width and candidate_rect[3] <= base.height
                )
                overlaps = any(
                    candidate_rect[0] < other[2] and candidate_rect[2] > other[0]
                    and candidate_rect[1] < other[3] and candidate_rect[3] > other[1]
                    for other in all_regions + label_rects
                )
                if inside_image and not overlaps:
                    position = (candidate_x, candidate_y, candidate_rect)
                    break
            if position:
                lx, ly, label_rect = position
            else:
                continue
            label_rects.append(label_rect)
            d.rounded_rectangle(
                [lx, ly, lx + badge_w, ly + badge_h],
                radius=max(3, pad // 2),
                fill=ImageColor.getrgb(badge_background) + (255,),
            )
            d.text((lx + pad - l, ly + pad - t), label, font=font, fill=ImageColor.getrgb(badge_text) + (255,))
    return Image.alpha_composite(base, layer).convert("RGB")