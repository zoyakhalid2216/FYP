"""Screen capture, OCR text locate, and template matching."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.vision.ocr_text import distinctive_tokens, normalize_ocr_query, normalize_ocr_text
from src.vision.search_result import (
    FIRST_RESULT_ELEMENT,
    is_first_result_phrase,
    is_ranked_result_phrase,
    link_bands_from_frame,
    list_search_results,
    parse_result_index,
    pick_search_result,
    text_matches_query,
)


@dataclass
class DetectionResult:
    found: bool
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    label: str = ""
    method: str = ""
    confidence: float = 0.0
    boxes: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def center(self) -> Tuple[int, int]:
        return self.x, self.y


class VisionEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = (config or {}).get("vision", {})
        paths = (config or {}).get("paths", {})
        self.ocr_lang = cfg.get("ocr_lang", "eng")
        self.template_threshold = float(cfg.get("template_threshold", 0.78))
        self.monitor_index = int(cfg.get("capture_monitor", 0))
        from src.config import resolve_path

        self.captures_dir = resolve_path(paths.get("captures_dir", "data/captures"))
        self.templates_dir = resolve_path(paths.get("templates_dir", "assets/templates"))
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self._last_frame_rgb: Optional[np.ndarray] = None
        self.last_region = {"left": 0, "top": 0, "width": 0, "height": 0}

    def capture_screen(self) -> np.ndarray:
        """Return RGB numpy array of the primary (or configured) monitor."""
        self._capture_ok = True
        self._capture_error = ""
        try:
            import mss
            from PIL import Image

            with mss.mss() as sct:
                monitors = sct.monitors
                idx = min(max(self.monitor_index, 0), len(monitors) - 1)
                # monitors[0] is virtual all; prefer monitors[1] when index 0 requested
                mon = monitors[1] if idx == 0 and len(monitors) > 1 else monitors[idx]
                shot = sct.grab(mon)
                img = Image.frombytes("RGB", shot.size, shot.rgb)
                frame = np.array(img)
                self.last_region = {
                    "left": int(mon.get("left") or 0),
                    "top": int(mon.get("top") or 0),
                    "width": int(frame.shape[1]),
                    "height": int(frame.shape[0]),
                }
        except Exception as exc:
            self._capture_ok = False
            self._capture_error = str(exc)
            # Headless / restricted environments: synthetic frame
            frame = np.zeros((540, 960, 3), dtype=np.uint8)
            frame[:] = (32, 40, 48)
            self.last_region = {"left": 0, "top": 0, "width": 960, "height": 540}
        self._last_frame_rgb = frame
        return frame

    @property
    def last_capture_ok(self) -> bool:
        return bool(getattr(self, "_capture_ok", True))

    @property
    def last_capture_error(self) -> str:
        return str(getattr(self, "_capture_error", ""))

    @property
    def last_frame(self) -> Optional[np.ndarray]:
        return self._last_frame_rgb

    def save_capture(
        self,
        frame: Optional[np.ndarray] = None,
        label: str = "capture",
        boxes: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        import cv2

        img = frame if frame is not None else self.capture_screen()
        bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        if boxes:
            for box in boxes:
                x, y, w, h = int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])
                cv2.rectangle(bgr, (x, y), (x + w, y + h), (0, 180, 80), 2)
                cv2.putText(
                    bgr,
                    str(box.get("label", "")),
                    (x, max(20, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 180, 80),
                    1,
                    cv2.LINE_AA,
                )
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:40]
        path = self.captures_dir / f"{safe_label}_{stamp}.png"
        cv2.imwrite(str(path), bgr)
        return str(path)

    def _tesseract_pass(self, gray, psm: int, min_conf: float = 15.0) -> List[Dict[str, Any]]:
        try:
            import pytesseract
            from pytesseract import Output
        except Exception:
            return []
        try:
            data = pytesseract.image_to_data(
                gray,
                lang=self.ocr_lang,
                output_type=Output.DICT,
                config=f"--oem 3 --psm {psm} -c preserve_interword_spaces=1",
            )
        except Exception:
            return []
        words: List[Dict[str, Any]] = []
        n = len(data.get("text", []))
        for i in range(n):
            text = normalize_ocr_text((data["text"][i] or "").strip())
            if not text:
                continue
            try:
                conf = float(data["conf"][i])
            except (ValueError, TypeError):
                conf = -1.0
            if conf < min_conf:
                continue
            words.append(
                {
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "w": data["width"][i],
                    "h": data["height"][i],
                    "label": text,
                    "conf": conf,
                    "line": data.get("line_num", [0] * n)[i],
                    "block": data.get("block_num", [0] * n)[i],
                }
            )
        return words

    def _ocr_scale_words(self, words: List[Dict[str, Any]], scale: float) -> List[Dict[str, Any]]:
        if not words or abs(scale - 1.0) < 0.01:
            return words
        out: List[Dict[str, Any]] = []
        for item in words:
            row = dict(item)
            for key in ("x", "y", "w", "h"):
                row[key] = int(round(int(row.get(key) or 0) / scale))
            out.append(row)
        return out

    def _ocr_preprocessed(self, img) -> Tuple[float, List[Any]]:
        """Gray / invert / contrast / adaptive variants, optionally upscaled for Tesseract."""
        import cv2

        h, w = img.shape[:2]
        scale = 1.0
        work = img
        if w < 1400:
            scale = 1.7 if w < 1100 else 1.4
            work = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(work, cv2.COLOR_RGB2GRAY)
        try:
            clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
            contrast = clahe.apply(gray)
        except Exception:
            contrast = gray
        inverted = cv2.bitwise_not(gray)
        inverted_c = cv2.bitwise_not(contrast)
        adaptive = cv2.adaptiveThreshold(
            contrast, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9
        )
        return scale, [gray, inverted, contrast, inverted_c, adaptive]

    def _ocr_words(self, img) -> List[Dict[str, Any]]:
        """Read UI text with several Tesseract passes (dark UI + small Google titles)."""
        from src.vision.ocr_text import merge_ocr_words

        if img is None or getattr(img, "size", 0) == 0:
            return []
        try:
            scale, variants = self._ocr_preprocessed(img)
        except Exception:
            return []
        primary = variants[:4]
        passes = [self._tesseract_pass(im, 11, min_conf=14.0) for im in primary]
        words = self._ocr_scale_words(merge_ocr_words(passes), scale)
        if len(words) < 14:
            extra = []
            for im in primary:
                extra.append(self._tesseract_pass(im, 6, min_conf=12.0))
            extra.append(self._tesseract_pass(variants[0], 4, min_conf=12.0))
            extra.append(self._tesseract_pass(variants[1], 4, min_conf=12.0))
            more = self._ocr_scale_words(merge_ocr_words(extra), scale)
            words = merge_ocr_words([words, more])
        panels = self._ocr_bright_panels(img)
        if panels:
            words = merge_ocr_words([words, panels])
        return words

    def _ocr_bright_panels(self, img) -> List[Dict[str, Any]]:
        """OCR white pill buttons (Horizon login) that get lost on a photo background."""
        import cv2

        try:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        except Exception:
            return []
        h, w = gray.shape[:2]
        _, mask = cv2.threshold(gray, 208, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 17), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        found: List[Dict[str, Any]] = []
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            if cw < 90 or ch < 20 or ch > 90 or cw > int(w * 0.55) or y < 50:
                continue
            y0, y1 = max(0, y - 4), min(h, y + ch + 4)
            x0, x1 = max(0, x - 4), min(w, x + cw + 4)
            crop = gray[y0:y1, x0:x1]
            crop = cv2.copyMakeBorder(crop, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
            for psm in (7, 6):
                for item in self._tesseract_pass(crop, psm, min_conf=10.0):
                    row = dict(item)
                    row["x"] = int(item.get("x") or 0) + x0 - 10
                    row["y"] = int(item.get("y") or 0) + y0 - 10
                    found.append(row)
        return found

    def find_text(self, query: str, frame: Optional[np.ndarray] = None) -> DetectionResult:
        """Locate on-screen text via Tesseract OCR and return center coordinates."""
        img = frame if frame is not None else self.capture_screen()
        query_l = normalize_ocr_query(query)
        if not query_l:
            return DetectionResult(found=False, label=query, method="ocr")
        if is_ranked_result_phrase(query_l) or is_first_result_phrase(query_l):
            return self.find_ranked_search_result(parse_result_index(query_l) or 1, img)

        words = self._ocr_words(img)
        boxes = list(words)
        if not words:
            return DetectionResult(found=False, label=query, method="ocr", confidence=0.0, boxes=boxes)

        best: Optional[DetectionResult] = None
        brands = distinctive_tokens(query_l)

        def consider(label: str, x: int, y: int, w: int, h: int, conf: float, *, bonus: float = 0.0) -> None:
            nonlocal best
            cx, cy = x + w // 2, y + h // 2
            score = max(0.0, min(1.0, conf / 100.0 + bonus))
            # Prefer the longest phrase that still matches (login With Microsoft > login).
            length = len((label or "").split())
            candidate = DetectionResult(
                found=True,
                x=cx,
                y=cy,
                width=w,
                height=h,
                label=label,
                method="ocr",
                confidence=score,
                boxes=boxes,
            )
            if best is None:
                best = candidate
                best._len = length  # type: ignore[attr-defined]
                return
            if length > getattr(best, "_len", 0) or (
                length == getattr(best, "_len", 0) and candidate.confidence > best.confidence
            ):
                best = candidate
                best._len = length  # type: ignore[attr-defined]

        for item in words:
            if text_matches_query(item["label"], query_l):
                consider(item["label"], item["x"], item["y"], item["w"], item["h"], item["conf"])

        rows: Dict[int, List[Dict[str, Any]]] = {}
        for item in words:
            rows.setdefault(int(item.get("y") or 0) // 16, []).append(item)
        for group in list(rows.values()):
            group.sort(key=lambda w: w["x"])
            for i in range(len(group)):
                for j in range(i + 1, min(len(group), i + 5) + 1):
                    chunk = group[i:j]
                    phrase = " ".join(w["label"] for w in chunk)
                    phrase_n = normalize_ocr_query(phrase)
                    if text_matches_query(phrase, query_l) or query_l == phrase_n or query_l in phrase_n:
                        x0 = chunk[0]["x"]
                        y0 = min(w["y"] for w in chunk)
                        x1 = chunk[-1]["x"] + chunk[-1]["w"]
                        y1 = max(w["y"] + w["h"] for w in chunk)
                        avg_conf = sum(w["conf"] for w in chunk) / max(1, len(chunk))
                        bonus = 0.15 if brands and all(b in phrase_n for b in brands) else 0.0
                        consider(phrase, x0, y0, x1 - x0, y1 - y0, avg_conf, bonus=bonus)

        if best:
            best.boxes = boxes
            return best
        return DetectionResult(found=False, label=query, method="ocr", boxes=boxes)

    def find_first_search_result(self, frame: Optional[np.ndarray] = None) -> DetectionResult:
        return self.find_ranked_search_result(1, frame)

    def find_ranked_search_result(
        self, index: int = 1, frame: Optional[np.ndarray] = None
    ) -> DetectionResult:
        img = frame if frame is not None else self.capture_screen()
        words = self._ocr_words(img)
        h, w = img.shape[:2]
        extra = link_bands_from_frame(img)
        ranked = list_search_results(words, w, h, extra_titles=extra)
        hit = pick_search_result(words, w, h, index=index, extra_titles=extra)
        if not hit:
            return DetectionResult(
                found=False,
                label=f"result {index}",
                method="search-result",
                boxes=list(ranked),
            )
        return DetectionResult(
            found=True,
            x=int(hit["x"] + hit["w"] // 2),
            y=int(hit["y"] + hit["h"] // 2),
            width=int(hit["w"]),
            height=int(hit["h"]),
            label=str(hit.get("label") or f"result {index}"),
            method="search-result",
            confidence=0.9,
            boxes=list(ranked),
        )

    def find_template(
        self, template_name: str, frame: Optional[np.ndarray] = None
    ) -> DetectionResult:
        """Match a template image from assets/templates against the screen."""
        import cv2

        img = frame if frame is not None else self.capture_screen()
        path = Path(template_name)
        if not path.is_file():
            path = self.templates_dir / template_name
        if not path.is_file():
            # try with common extensions
            for ext in (".png", ".jpg", ".jpeg", ".bmp"):
                candidate = self.templates_dir / f"{template_name}{ext}"
                if candidate.is_file():
                    path = candidate
                    break
        if not path.is_file():
            return DetectionResult(found=False, label=template_name, method="template")

        template = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if template is None:
            return DetectionResult(found=False, label=template_name, method="template")
        screen_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        result = cv2.matchTemplate(screen_bgr, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        th, tw = template.shape[:2]
        if max_val < self.template_threshold:
            return DetectionResult(
                found=False,
                label=template_name,
                method="template",
                confidence=float(max_val),
            )
        x, y = max_loc[0] + tw // 2, max_loc[1] + th // 2
        box = {"x": max_loc[0], "y": max_loc[1], "w": tw, "h": th, "label": template_name}
        return DetectionResult(
            found=True,
            x=x,
            y=y,
            width=tw,
            height=th,
            label=template_name,
            method="template",
            confidence=float(max_val),
            boxes=[box],
        )

    def locate(
        self,
        element: str,
        prefer: str = "ocr",
        frame: Optional[np.ndarray] = None,
    ) -> DetectionResult:
        img = frame if frame is not None else self.capture_screen()
        if not (element or "").strip():
            return DetectionResult(found=False, label="", method="ocr")
        idx = parse_result_index(element)
        if element == FIRST_RESULT_ELEMENT or is_ranked_result_phrase(element) or idx:
            return self.find_ranked_search_result(idx or 1, img)
        if prefer == "template":
            hit = self.find_template(element, img)
            if hit.found:
                return hit
            return self.find_text(element, img)
        hit = self.find_text(element, img)
        if hit.found:
            return hit
        return self.find_template(element, img)

    def frame_changed(
        self,
        before,
        after,
        *,
        threshold: float = 0.018,
    ) -> Dict[str, Any]:
        """Compare two RGB frames; used to verify that a click/open actually changed the UI."""
        import numpy as np

        if before is None or after is None:
            return {"changed": True, "score": 1.0, "note": "missing frame"}
        a = np.asarray(before)
        b = np.asarray(after)
        if a.shape != b.shape:
            return {"changed": True, "score": 1.0, "note": "size changed"}
        diff = float(np.mean(np.abs(a.astype("float32") - b.astype("float32"))) / 255.0)
        return {"changed": diff >= threshold, "score": round(diff, 4), "note": ""}

    def ocr_preview(self, frame=None, max_boxes: int = 24) -> DetectionResult:
        """Run OCR for the AI Agent screen-understanding panel."""
        img = frame if frame is not None else self.capture_screen()
        dummy = self.find_text("___no_match___", frame=img)
        dummy.found = bool(dummy.boxes)
        dummy.boxes = (dummy.boxes or [])[:max_boxes]
        dummy.label = f"{len(dummy.boxes)} OCR boxes"
        dummy.method = "ocr-preview"
        return dummy
