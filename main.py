"""
Defect Detection API (Fabric, Shoe, ... any Roboflow model)

- Multiple "profiles" (e.g. Fabric, Shoe), each with its own Roboflow API key,
  model ID and confidence. Switch the active profile from the Settings page.
- Uploaded images are sent to Roboflow cloud inference.
- Returns detections + an annotated (predicted) image.
- Saves original image, predicted image and JSON result for every upload.
"""
import base64
import io
import json
import os
import re
import threading
import uuid
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont, ImageOps

load_dotenv()  # .env is only used to create the first profile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
ORIGINAL_DIR = os.path.join(OUTPUT_DIR, "original")    # images exactly as uploaded
PREDICTED_DIR = os.path.join(OUTPUT_DIR, "predicted")  # images with defect boxes drawn
RESULTS_DIR = os.path.join(OUTPUT_DIR, "results")      # JSON result for each image
for _d in (ORIGINAL_DIR, PREDICTED_DIR, RESULTS_DIR):
    os.makedirs(_d, exist_ok=True)

DEFAULT_API_URL = "https://serverless.roboflow.com"
ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB

# Fixed colours for common classes; anything else gets a colour from the palette.
CLASS_COLORS = {
    "hole": (230, 57, 70),
    "oil_spot": (255, 159, 28),
    "stain": (255, 159, 28),
    "thread_error": (58, 134, 255),
    "defect": (220, 38, 127),
    "objects": (46, 196, 182),
}
PALETTE = [(131, 56, 236), (6, 214, 160), (255, 0, 110), (251, 86, 7), (0, 180, 216), (90, 120, 40)]


# =============================================================== auto naming
# Keyword in the model ID  ->  display name
NAME_KEYWORDS = [
    (("fabric", "textile", "cloth", "denim", "weav", "yarn", "garment"), "Fabric"),
    (("shoe", "footwear", "sneaker", "sole", "boot"), "Shoe"),
    (("leather",), "Leather"),
    (("pcb", "circuit", "solder"), "PCB"),
    (("weld",), "Weld"),
    (("steel", "metal"), "Metal"),
    (("wood", "timber", "plank"), "Wood"),
    (("glass",), "Glass"),
    (("tile", "ceramic"), "Tile"),
    (("bottle",), "Bottle"),
    (("tyre", "tire"), "Tyre"),
    (("concrete", "crack", "wall"), "Surface"),
    (("paper", "carton", "package", "box"), "Packaging"),
    (("casting",), "Casting"),
]
NOISE_WORDS = {"yolo", "yolov5", "yolov8", "yolov11", "detector", "detection", "detect", "defect", "defects",
               "model", "dataset", "project", "my", "first", "new", "final", "test", "roboflow", "object", "objects"}


def suggest_name(model_id: str) -> str:
    """Guess a friendly product name from a Roboflow model ID, e.g.
    'yolo-fabric-defect-detector/1' -> 'Fabric', 'shoe-sole-defects-x7k2p/3' -> 'Shoe'."""
    slug = (model_id or "").split("/")[0].lower()
    for words, name in NAME_KEYWORDS:
        if any(w in slug for w in words):
            return name
    parts = [p for p in re.split(r"[-_\s]+", slug) if p]
    if parts and re.fullmatch(r"[a-z0-9]{5}", parts[-1]) and re.search(r"\d", parts[-1]):
        parts = parts[:-1]  # drop Roboflow's random suffix like 'aqnck' / 'm9wg4'
    parts = [p for p in parts if p not in NOISE_WORDS and not re.fullmatch(r"v?\d+", p)]
    return " ".join(p.capitalize() for p in parts) or "Product"


def make_profile_id(name: str, existing) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "profile").lower()).strip("-") or "profile"
    pid, i = base, 2
    while pid in existing:
        pid, i = f"{base}-{i}", i + 1
    return pid


# =============================================================== settings store
_lock = threading.Lock()


def _default_settings() -> dict:
    model_id = os.getenv("MODEL_ID", "yolo-fabric-defect-detector/1")
    key = os.getenv("ROBOFLOW_API_KEY", "")
    if key == "YOUR_API_KEY":
        key = ""
    name = suggest_name(model_id)
    pid = make_profile_id(name, set())
    return {
        "active": pid,
        "profiles": {
            pid: {
                "name": name,
                "title": f"{name} Defect Inspection",
                "model_id": model_id,
                "api_key": key,
                "api_url": os.getenv("ROBOFLOW_API_URL", DEFAULT_API_URL),
                "confidence": float(os.getenv("CONFIDENCE", "0.4")),
            }
        },
    }


def load_settings() -> dict:
    with _lock:
        if not os.path.exists(SETTINGS_FILE):
            s = _default_settings()
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=2)
            return s
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            s = json.load(f)
    if not s.get("profiles"):
        s = _default_settings()
    if s.get("active") not in s["profiles"]:
        s["active"] = next(iter(s["profiles"]))
    return s


def save_settings(s: dict):
    with _lock:
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
        os.replace(tmp, SETTINGS_FILE)


def active_profile() -> dict:
    s = load_settings()
    p = dict(s["profiles"][s["active"]])
    p["id"] = s["active"]
    return p


def mask_key(key: str) -> str:
    if not key:
        return ""
    return key[:4] + "•" * 8 + key[-2:] if len(key) > 8 else "•" * len(key)


def public_profile(pid: str, p: dict, active: str) -> dict:
    return {
        "id": pid,
        "name": p.get("name"),
        "title": p.get("title") or f'{p.get("name")} Defect Inspection',
        "model_id": p.get("model_id"),
        "api_url": p.get("api_url") or DEFAULT_API_URL,
        "confidence": p.get("confidence", 0.4),
        "api_key_masked": mask_key(p.get("api_key", "")),
        "has_api_key": bool(p.get("api_key")),
        "active": pid == active,
    }


# =============================================================== app
app = FastAPI(
    title="Defect Detection API",
    description="Upload an image to detect defects using a Roboflow model. "
    "Profiles (Fabric, Shoe, ...) are managed on the Settings page.",
    version="5.1.0",
)
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# =============================================================== helpers
def roboflow_infer(image_bytes: bytes, confidence: float, profile: dict) -> dict:
    """Send an image to Roboflow's hosted API (works on any Python version)."""
    if not profile.get("api_key"):
        raise RuntimeError("No Roboflow API key set for this profile. Add it on the Settings page.")
    url = f"{(profile.get('api_url') or DEFAULT_API_URL).rstrip('/')}/{profile['model_id']}"
    resp = requests.post(
        url,
        params={"api_key": profile["api_key"], "confidence": confidence},
        data=base64.b64encode(image_bytes).decode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def color_for(cls: str):
    key = (cls or "").lower()
    if key in CLASS_COLORS:
        return CLASS_COLORS[key]
    return PALETTE[sum(map(ord, key)) % len(PALETTE)]


def load_font(size: int):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def has_box(d: dict) -> bool:
    return all(isinstance(d.get(k), (int, float)) for k in ("x", "y", "width", "height"))


def annotate(image_bytes: bytes, defects: list, profile: dict, task: str = "detection") -> bytes:
    """Draw a labelled box for each defect (detection/segmentation) or a label strip
    for whole-image results (classification). Returns JPEG bytes."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    line = max(2, round(min(w, h) / 200))
    font = load_font(max(12, round(min(w, h) / 35)))
    pad = max(2, line)

    # ---- boxes (object detection / instance segmentation)
    for d in defects:
        if not has_box(d):
            continue
        x0, y0 = d["x"] - d["width"] / 2, d["y"] - d["height"] / 2
        x1, y1 = d["x"] + d["width"] / 2, d["y"] + d["height"] / 2
        col = color_for(d["class"])
        draw.rectangle([x0, y0, x1, y1], outline=col, width=line)

        label = f'{d["class"]} {d["confidence"] * 100:.0f}%'
        tb = draw.textbbox((0, 0), label, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        ly = y0 - th - 2 * pad if y0 - th - 2 * pad >= 0 else y0
        lx = min(max(0, x0), max(0, w - tw - 2 * pad))
        draw.rectangle([lx, ly, lx + tw + 2 * pad, ly + th + 2 * pad], fill=col)
        draw.text((lx + pad, ly + pad - tb[1]), label, fill=(255, 255, 255), font=font)

    # ---- whole-image labels (classification): coloured tags in the top-left corner
    y = pad
    for d in [d for d in defects if not has_box(d)]:
        label = f'{d["class"]} {d["confidence"] * 100:.0f}%'
        tb = draw.textbbox((0, 0), label, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        draw.rectangle([pad, y, pad + tw + 3 * pad, y + th + 3 * pad], fill=color_for(d["class"]))
        draw.text((pad + 1.5 * pad, y + 1.5 * pad - tb[1]), label, fill=(255, 255, 255), font=font)
        y += th + 4 * pad

    if task == "classification":
        summary = f'{profile.get("name", "")}: ' + (", ".join(d["class"] for d in defects) or "no class above threshold") \
                  + f' | {profile.get("model_id", "")}'
    else:
        summary = f'{profile.get("name", "")}: {len(defects)} defect(s) | {profile.get("model_id", "")}'
    sb = draw.textbbox((0, 0), summary, font=font)
    draw.rectangle([0, h - (sb[3] - sb[1]) - 12, sb[2] - sb[0] + 12, h], fill=(0, 0, 0))
    draw.text((6, h - (sb[3] - sb[1]) - 6 - sb[1]), summary, fill=(255, 255, 255), font=font)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92)
    return out.getvalue()


def read_upload(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Upload JPG, PNG or WEBP images only")
    data = file.file.read()
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image must be non-empty and under 10 MB")
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception:
        raise HTTPException(status_code=400, detail="File is not a valid image")
    return data


def parse_predictions(result: dict, confidence: float):
    """Normalise Roboflow responses into (task, defects).
    - Object detection / instance segmentation: list of boxes with x, y, width, height
    - Single-label classification: list of {class, confidence} (+ 'top')  -> best class only
    - Multi-label classification: dict {class: {confidence}}              -> every class above threshold
    """
    preds = result.get("predictions", [])

    if isinstance(preds, dict):  # multi-label classification
        items = [{"class": c, "confidence": float((v or {}).get("confidence", 0))} for c, v in preds.items()]
        items = [i for i in items if i["confidence"] >= confidence]
        items.sort(key=lambda i: -i["confidence"])
        return "classification", [{**i, "confidence": round(i["confidence"], 3),
                                   "x": None, "y": None, "width": None, "height": None} for i in items]

    if preds and not any(has_box(p) for p in preds):  # single-label classification
        best = max(preds, key=lambda p: p.get("confidence", 0))
        top_class = result.get("top", best.get("class"))
        top_conf = float(result.get("confidence", best.get("confidence", 0)))
        items = [] if top_conf < confidence else [{
            "class": top_class, "confidence": round(top_conf, 3),
            "x": None, "y": None, "width": None, "height": None}]
        return "classification", items

    task = "segmentation" if any(p.get("points") for p in preds) else "detection"
    return task, [
        {
            "class": p.get("class"),
            "confidence": round(p.get("confidence", 0), 3),
            "x": p.get("x"),
            "y": p.get("y"),
            "width": p.get("width"),
            "height": p.get("height"),
        }
        for p in preds
        if has_box(p) and p.get("confidence", 0) >= confidence
    ]


def run_detection(image_bytes: bytes, confidence: float, profile: dict):
    try:
        result = roboflow_infer(image_bytes, confidence, profile)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cloud inference failed: {e}")
    task, defects = parse_predictions(result, confidence)
    return result, task, defects, annotate(image_bytes, defects, profile, task)


def save_outputs(original: bytes, annotated: bytes, upload: UploadFile, payload: dict) -> dict:
    """Save original image, predicted image and JSON result with the same base name."""
    stem = os.path.splitext(os.path.basename(upload.filename or "image"))[0][:40]
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem) or "image"
    prefix = re.sub(r"[^a-z0-9]+", "", (payload.get("profile_name") or "").lower())[:12]
    base = f"{datetime.now():%Y%m%d_%H%M%S}_{prefix + '_' if prefix else ''}{stem}_{uuid.uuid4().hex[:6]}"

    original_name = base + ALLOWED_TYPES.get(upload.content_type, ".jpg")
    predicted_name = base + "_predicted.jpg"
    result_name = base + ".json"

    with open(os.path.join(ORIGINAL_DIR, original_name), "wb") as f:
        f.write(original)
    with open(os.path.join(PREDICTED_DIR, predicted_name), "wb") as f:
        f.write(annotated)

    files = {
        "original_image_url": f"/outputs/original/{original_name}",
        "predicted_image_url": f"/outputs/predicted/{predicted_name}",
        "result_json_url": f"/outputs/results/{result_name}",
        "original_image_file": os.path.join(ORIGINAL_DIR, original_name),
        "predicted_image_file": os.path.join(PREDICTED_DIR, predicted_name),
    }
    with open(os.path.join(RESULTS_DIR, result_name), "w", encoding="utf-8") as f:
        json.dump({"saved_at": datetime.now().isoformat(timespec="seconds"), **payload, **files}, f, indent=2)
    return files


def detect_and_save(file: UploadFile, confidence: Optional[float]):
    profile = active_profile()
    conf = profile.get("confidence", 0.4) if confidence is None else confidence
    image_bytes = read_upload(file)
    result, task, defects, annotated = run_detection(image_bytes, conf, profile)
    payload = {
        "status": "success",
        "task": task,
        "uploaded_filename": file.filename,
        "profile_id": profile["id"],
        "profile_name": profile.get("name"),
        "model_id": profile.get("model_id"),
        "confidence_threshold": conf,
        "total_defects": len(defects),
        "defects": defects,
        "image": result.get("image"),
        "inference_time_s": result.get("time"),
    }
    payload.update(save_outputs(image_bytes, annotated, file, payload))
    return payload, annotated


# =============================================================== pages
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/ui")


@app.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/ui/settings", include_in_schema=False)
def ui_settings():
    return FileResponse(os.path.join(STATIC_DIR, "settings.html"))


# =============================================================== detection endpoints
@app.get("/health")
def health():
    p = active_profile()
    return {
        "status": "running",
        "profile_id": p["id"],
        "profile_name": p.get("name"),
        "title": p.get("title"),
        "model_id": p.get("model_id"),
        "default_confidence": p.get("confidence", 0.4),
        "api_key_set": bool(p.get("api_key")),
    }


@app.post("/detect")
def detect_defects(
    file: UploadFile = File(...),
    confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence 0–1 (default: profile setting)"),
    include_base64: bool = Query(False, description="Also return the predicted image as base64"),
):
    """Detect defects with the ACTIVE profile. Returns JSON with defects and image links."""
    payload, annotated = detect_and_save(file, confidence)
    if include_base64:
        payload["annotated_image_base64"] = "data:image/jpeg;base64," + base64.b64encode(annotated).decode()
    return payload


@app.post(
    "/detect/image",
    responses={200: {"content": {"image/jpeg": {}}, "description": "Annotated JPEG image"}},
    response_class=Response,
)
def detect_defects_image(
    file: UploadFile = File(...),
    confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence 0–1"),
):
    """Detect defects with the ACTIVE profile and return the predicted image directly (JPEG)."""
    payload, annotated = detect_and_save(file, confidence)
    return Response(
        content=annotated,
        media_type="image/jpeg",
        headers={
            "X-Profile": payload["profile_name"] or "",
            "X-Total-Defects": str(payload["total_defects"]),
            "X-Defect-Classes": ",".join(sorted({d["class"] for d in payload["defects"]})) or "none",
            "X-Original-Image-Url": payload["original_image_url"],
            "X-Predicted-Image-Url": payload["predicted_image_url"],
        },
    )


@app.get("/history")
def history(
    limit: int = Query(50, ge=1, le=500),
    profile_id: Optional[str] = Query(None, description="Only results from this profile"),
):
    """List the most recent detection results (newest first)."""
    names = sorted((f for f in os.listdir(RESULTS_DIR) if f.endswith(".json")), reverse=True)
    items = []
    for name in names:
        if len(items) >= limit:
            break
        try:
            with open(os.path.join(RESULTS_DIR, name), encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        if profile_id and d.get("profile_id") != profile_id:
            continue
        items.append({k: d.get(k) for k in (
            "uploaded_filename", "saved_at", "task", "profile_id", "profile_name", "model_id", "confidence_threshold",
            "total_defects", "defects", "original_image_url", "predicted_image_url", "result_json_url")})
    return {"count": len(items), "items": items}


# =============================================================== settings endpoints
@app.get("/settings")
def get_settings():
    """All profiles (API keys are masked) and which one is active."""
    s = load_settings()
    return {
        "active": s["active"],
        "profiles": [public_profile(pid, p, s["active"]) for pid, p in s["profiles"].items()],
    }


@app.get("/settings/suggest-name")
def settings_suggest_name(model_id: str):
    """Suggest a display name and title from a model ID."""
    name = suggest_name(model_id)
    return {"name": name, "title": f"{name} Defect Inspection"}


@app.post("/settings/profiles")
def save_profile(data: dict = Body(..., examples=[{
    "id": None, "name": "Shoe", "title": "Shoe Defect Inspection", "model_id": "shoe-defects-abc12/1",
    "api_key": "", "api_url": DEFAULT_API_URL, "confidence": 0.4, "activate": True}])):
    """Create a profile (no id) or update one (with id).
    Empty api_key = keep the current key (or copy the active profile's key for a new profile)."""
    model_id = (data.get("model_id") or "").strip().strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+/\d+", model_id):
        raise HTTPException(status_code=400, detail="Model ID must look like 'project-name/1' (project/version)")
    try:
        confidence = float(data.get("confidence", 0.4))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Confidence must be a number between 0 and 1")
    if not 0 <= confidence <= 1:
        raise HTTPException(status_code=400, detail="Confidence must be between 0 and 1")

    s = load_settings()
    pid = data.get("id")
    if pid and pid not in s["profiles"]:
        raise HTTPException(status_code=404, detail="Profile not found")

    name = (data.get("name") or "").strip() or suggest_name(model_id)
    title = (data.get("title") or "").strip() or f"{name} Defect Inspection"
    new_key = (data.get("api_key") or "").strip()
    if pid:
        api_key = new_key or s["profiles"][pid].get("api_key", "")
    else:
        api_key = new_key or s["profiles"][s["active"]].get("api_key", "")
        pid = make_profile_id(name, s["profiles"].keys())

    s["profiles"][pid] = {
        "name": name,
        "title": title,
        "model_id": model_id,
        "api_key": api_key,
        "api_url": (data.get("api_url") or DEFAULT_API_URL).strip().rstrip("/"),
        "confidence": confidence,
    }
    if data.get("activate"):
        s["active"] = pid
    save_settings(s)
    return {"saved": pid, **get_settings()}


@app.post("/settings/active")
def set_active(data: dict = Body(..., examples=[{"id": "fabric"}])):
    """Switch the active profile (used by /detect and the UI)."""
    s = load_settings()
    pid = data.get("id")
    if pid not in s["profiles"]:
        raise HTTPException(status_code=404, detail="Profile not found")
    s["active"] = pid
    save_settings(s)
    return get_settings()


@app.delete("/settings/profiles/{pid}")
def delete_profile(pid: str):
    s = load_settings()
    if pid not in s["profiles"]:
        raise HTTPException(status_code=404, detail="Profile not found")
    if len(s["profiles"]) == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only profile")
    del s["profiles"][pid]
    if s["active"] == pid:
        s["active"] = next(iter(s["profiles"]))
    save_settings(s)
    return get_settings()


@app.post("/settings/test")
def test_connection(data: dict = Body(..., examples=[{"id": "fabric", "model_id": "", "api_key": "", "api_url": ""}])):
    """Check that the API key + model work by sending a small blank image to Roboflow.
    Blank fields fall back to the saved profile given by id (or the active profile)."""
    s = load_settings()
    base = s["profiles"].get(data.get("id") or s["active"], {})
    profile = {
        "model_id": (data.get("model_id") or base.get("model_id") or "").strip().strip("/"),
        "api_key": (data.get("api_key") or base.get("api_key") or "").strip(),
        "api_url": (data.get("api_url") or base.get("api_url") or DEFAULT_API_URL).strip(),
    }
    if not profile["model_id"]:
        raise HTTPException(status_code=400, detail="Model ID is required")
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 200, 200)).save(buf, "JPEG")
    try:
        r = roboflow_infer(buf.getvalue(), 0.5, profile)
    except Exception as e:
        msg = str(e)
        hint = ""
        if "401" in msg or "403" in msg:
            hint = "API key is wrong or has no access to this model."
        elif "404" in msg:
            hint = "Model ID not found. Check the project name and version number."
        elif "No Roboflow API key" in msg:
            hint = "Enter the API key."
        return {"ok": False, "error": msg, "hint": hint}
    return {
        "ok": True,
        "model_id": profile["model_id"],
        "resolved_model": r.get("resolved_model"),
        "suggested_name": suggest_name(profile["model_id"]),
    }
