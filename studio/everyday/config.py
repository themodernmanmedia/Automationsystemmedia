"""Global settings for the Everyday Beast animation studio."""
from __future__ import annotations

import os
from pathlib import Path

# Logical canvas. Everything is drawn in 1920x1080 units; preview renders
# simply scale the cairo context down.
W, H = 1920, 1080
FPS = 30

STUDIO_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = STUDIO_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
CACHE_DIR = Path(os.environ.get("EVERYDAY_CACHE", STUDIO_DIR / ".cache"))
OUT_DIR = Path(os.environ.get("EVERYDAY_OUT", STUDIO_DIR / "output"))
MODELS_DIR = Path(os.environ.get("EVERYDAY_MODELS", STUDIO_DIR / "models"))

KOKORO_MODEL = MODELS_DIR / "kokoro-v1.0.onnx"
KOKORO_VOICES = MODELS_DIR / "voices-v1.0.bin"
KOKORO_URLS = {
    KOKORO_MODEL.name: "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    KOKORO_VOICES.name: "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}

SAMPLE_RATE = 48000

# Fonts (Anton ships in assets/fonts; Inter/DejaVu are system fallbacks).
FONT_HEADLINE = "Anton"
FONT_UI = "Inter, DejaVu Sans"
