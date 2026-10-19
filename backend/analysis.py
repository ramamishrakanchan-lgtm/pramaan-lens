"""Rule-based, offline analysis. Every flag points to an image region or a metadata field.
No generative LLM, and no genuine/fake verdict: only HIGH / MEDIUM / LOW risk flags."""
import io, re, datetime as dt
import cv2, numpy as np, imagehash
from PIL import Image, ImageDraw, ImageFont, ImageColor, ExifTags
from . import custody

EDITORS = ("photoshop", "gimp", "canva", "snapseed", "picsart", "pixlr", "lightroom", "paint.net", "figma", "fotor")
RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
COLORS = {"HIGH": "#B3342F", "MEDIUM": "#C98A1B", "LOW": "#4F7A64"}
DATE_RE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})")
REL_RE = re.compile(r"today|yesterday")


def _flag(check, obs, level, action, region=None, field=None):
    return dict(check=check, observation=obs, level=level, action=action, region=region, field=field)


def _hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


# 1. Metadata -----------------------------------------------------------
def metadata(img):
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
    for k in ("DateTimeOriginal", "DateTime"):
        try:
            return dt.datetime.strptime(info[k][:19], "%Y:%m:%d %H:%M:%S")
        except (KeyError, ValueError):
            continue
    return None


# 2. OCR ----------------------------------------------------------------
def ocr_words(img):
    import pytesseract
    d = pytesseract.image_to_data(img.convert("RGB"), output_type=pytesseract.Output.DICT)
    return [dict(t=d["text"][i].strip(), box=(d["left"][i], d["top"][i], d["width"][i], d["height"][i]))
            for i in range(len(d["text"])) if d["text"][i].strip()]


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
def ela_flags(img):
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
    return [_flag("UI consistency", "Compression level differs in this region (ELA is noisy on screenshots)",
                  "LOW", "Inspect this region visually", region=tuple(int(v) for v in b)) for b in boxes]


# 5. Reuse detection --------------------------------------------------------
def reuse_flags(ph, case_id):
    return [_flag("Reuse detection", f"Perceptually similar to earlier case {cid} (distance {ph - imagehash.hex_to_hash(hx)})",
                  "HIGH", "Compare with the earlier case file", field=f"phash:{cid}")
            for cid, hx in custody.previous(case_id) if ph - imagehash.hex_to_hash(hx) <= 6]


# Pipeline ----------------------------------------------------------------
def analyze(raw: bytes, filename: str, claimed=None):
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
    flags += order_flags(words) + date_flags(words, capture_time(info), claimed) + ela_flags(img)
    ph = imagehash.phash(img)
    flags += reuse_flags(ph, case_id)
    custody.register(case_id, digest, str(ph), filename)
    custody.log(case_id, "ANALYSED", f"{len(flags)} flags, ocr_words={len(words)}")
    flags.sort(key=lambda f: -RANK[f["level"]])
    return dict(case_id=case_id, sha256=digest, filename=filename, flags=flags, metadata=info, image=img,
                top=flags[0]["level"] if flags else "LOW")


# 6. Annotated image (clear boxes + labels) -----------------------------------
BOX = {"HIGH": "#E5322D", "MEDIUM": "#F59E0B", "LOW": "#10B981"}


def _font(size):
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate(img, flags):
    base = img.convert("RGBA")
    scale = max(base.size) / 800
    lw = max(4, round(4 * scale))
    fs = max(14, round(16 * scale))
    font = _font(fs)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for f in sorted(flags, key=lambda f: RANK[f["level"]]):  # HIGH sabse upar
        if not f["region"]:
            continue
        x, y, w, h = f["region"]
        rgb = ImageColor.getrgb(BOX[f["level"]])
        d.rectangle([x, y, x + w, y + h], fill=rgb + (45,), outline=rgb + (255,), width=lw)
        label = f"{f['level']} - {f['check']}"
        l, t, r, b = d.textbbox((0, 0), label, font=font)
        tw, th, pad = r - l, b - t, max(3, fs // 4)
        ly = y - th - 2 * pad - lw
        if ly < 0:  # upar jagah nahi hai to box ke neeche
            ly = min(y + h + lw, max(0, base.height - th - 2 * pad))
        lx = min(max(0, x), max(0, base.width - tw - 2 * pad))
        d.rectangle([lx, ly, lx + tw + 2 * pad, ly + th + 2 * pad], fill=rgb + (255,))
        d.text((lx + pad - l, ly + pad - t), label, font=font, fill=(255, 255, 255, 255))
    return Image.alpha_composite(base, layer).convert("RGB")