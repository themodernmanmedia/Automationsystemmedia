"""Make the bundled fonts visible to cairo through a private fontconfig file.

Must run before cairo renders any text, so it is imported first by the package.
"""
from __future__ import annotations

import os
import tempfile

from .config import FONTS_DIR, CACHE_DIR


def install() -> None:
    if os.environ.get("EVERYDAY_FONTCONFIG_DONE"):
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conf = CACHE_DIR / "fonts.conf"
    conf.write_text(
        f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
  <dir>{FONTS_DIR}</dir>
  <cachedir>{CACHE_DIR / 'fontcache'}</cachedir>
</fontconfig>
"""
    )
    os.environ["FONTCONFIG_FILE"] = str(conf)
    os.environ["EVERYDAY_FONTCONFIG_DONE"] = "1"


install()
