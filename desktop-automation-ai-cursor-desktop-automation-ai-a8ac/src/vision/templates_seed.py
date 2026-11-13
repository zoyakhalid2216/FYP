"""Generate starter OpenCV template assets for UI matching demos."""

from __future__ import annotations

from pathlib import Path


def ensure_template_assets(templates_dir: Path) -> list[str]:
    """Create simple button/icon templates if the folder is empty."""
    templates_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return created

    specs = [
        ("button_ok.png", "OK", (34, 120, 80), (255, 255, 255), (120, 40)),
        ("button_cancel.png", "Cancel", (120, 50, 50), (255, 255, 255), (140, 40)),
        ("button_login.png", "Login", (17, 24, 39), (255, 255, 255), (140, 42)),
        ("button_search.png", "Search", (37, 99, 235), (255, 255, 255), (150, 42)),
        ("button_submit.png", "Submit", (15, 118, 110), (255, 255, 255), (150, 42)),
        ("icon_chrome.png", "C", (66, 133, 244), (255, 255, 255), (48, 48)),
    ]
    for name, label, fill, ink, size in specs:
        path = templates_dir / name
        if path.exists():
            continue
        img = Image.new("RGB", size, fill)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        # Center-ish text
        tw = len(label) * 6
        th = 10
        draw.text(((size[0] - tw) // 2, (size[1] - th) // 2), label, fill=ink, font=font)
        # Border helps template matching edges
        draw.rectangle([0, 0, size[0] - 1, size[1] - 1], outline=(255, 255, 255))
        img.save(path)
        created.append(str(path))
    return created


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    out = root / "assets" / "templates"
    print(ensure_template_assets(out))
