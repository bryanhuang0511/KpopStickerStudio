# KpopStickerStudio

[English](README.md) | [中文 (繁體)](README_zh.md)

A command-line sticker and meme processing engine designed for lossless pixel preservation. It executes cropping, downscale-only resizing, optional offline background removal with outline generation, rounded corners, meme text bars, and outlined multi-language captions without applying generative edits, skin smoothing, or color filters to source images.

---

## File List and Component Roles

| File / Directory | Role | Core Responsibility |
|---|---|---|
| [`make_sticker.py`](make_sticker.py) | Single-Image CLI Entry | Parses command-line arguments and renders a single sticker or meme |
| [`make_batch.py`](make_batch.py) | Batch CLI Entry | Executes a JSON job manifest and optionally generates a verification contact sheet |
| [`config.json`](config.json) | Default Configuration | Stores default output directory, resolution limits, cutout models, and typography settings |
| [`src/sticker_maker/renderer.py`](src/sticker_maker/renderer.py) | Core Rendering Pipeline | Handles EXIF orientation, border trimming, normalized/aspect cropping, resizing, and text compositing |
| [`src/sticker_maker/cutout.py`](src/sticker_maker/cutout.py) | Offline Cutout Module | Runs `birefnet-portrait` (with `isnet-general-use` fallback), alpha smoothing, outline, and mask quality checks |
| [`src/sticker_maker/fonts.py`](src/sticker_maker/fonts.py) | Font & Glyph Resolver | Resolves Traditional Chinese / Hangul / CJK fonts and detects unsupported characters (`.notdef` tofu boxes) |
| [`src/sticker_maker/naming.py`](src/sticker_maker/naming.py) | Output Naming Guard | Sanitizes filenames, formats `<person>_<text>.<ext>`, and prevents accidental overwrites |
| [`src/sticker_maker/batch.py`](src/sticker_maker/batch.py) | Batch Runner & QA Sheet | Runs manifest jobs into group/member directories and compiles labeled verification sheets |
| [`src/sticker_maker/config.py`](src/sticker_maker/config.py) | Configuration Loader | Loads `config.json` and expands user home paths |
| [`tests/test_studio.py`](tests/test_studio.py) | Automated Test Suite | Verifies pixel preservation, border trimming, glyph checks, batch output, and CLI behavior |

---

## Processing Modes and Default Configuration

### Rendering Modes

| Mode (`--mode`) | Description | Default Max Edge (`--max-size`) |
|---|---|---|
| `original` | Crops source image, downscales only if larger than `max_size`, and overlays outlined text | `1024 px` |
| `cutout` | Performs offline background removal preserving original foreground RGB pixels, adds outline & shadow | `512 px` |
| `meme-bar` | Appends a solid top or bottom caption bar outside the image frame so the source image remains unobstructed | `1024 px` |

### Default Parameters (`config.json`)

| Setting | Default | Notes |
|---|---|---|
| `default_output_dir` | `~/Pictures/貼圖` | Overridable via `--out-dir` |
| `default_format` | `png` | Supports `png` (lossless), `webp` (lossless), and `jpg` (quality 95, 4:4:4) |
| `default_cutout_model` | `birefnet-portrait` | Falls back to `isnet-general-use` on failure |
| `default_font_preset` | `bold` | Presets: `bold`, `heavy`, `sans`, `serif`, `kai`, `kr` (auto-switches when Hangul is detected) |
| `default_text_style` | `classic` | Styles: `classic`, `heavy`, `yellow`, `pink`, `blue`, `dark`, `bar` |
| `default_text_scale` | `0.11` | Text height relative to the shorter output edge; stroke ratio defaults to `0.068` |

### Font Glyph Safeguard

Windows CJK system fonts (`NotoSansTC-VF.ttf`, `msjhbd.ttc`) do not include color emojis (for example, `🙏` renders as a missing-glyph box). Basic symbols such as `♡` are supported. The renderer inspects each character via `find_unsupported_chars` and reports unsupported glyphs in `warnings` (stdout and `--json` output).

---

## Installation and Usage

### Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

### Single-Image CLI Examples

```powershell
# 1. 1:1 crop with bottom white text and black stroke
.\.venv\Scripts\python.exe make_sticker.py "path\to\photo.jpg" --person "Wonhee" --text "在幹嘛" --aspect 1:1

# 2. Auto-trim uniform white/black screenshot borders before 1:1 crop
.\.venv\Scripts\python.exe make_sticker.py "path\to\screenshot.jpg" --person "Minju" --text "收到！" --auto-trim --aspect 1:1

# 3. Offline background removal on a square transparent canvas
.\.venv\Scripts\python.exe make_sticker.py "path\to\photo.jpg" --person "Ahyeon" --text "吃瓜中" --mode cutout --square-canvas

# 4. External caption bar without covering the image
.\.venv\Scripts\python.exe make_sticker.py "path\to\photo.jpg" --person "Rora" --text "已讀亂回" --mode meme-bar --bar-pos bottom

# 5. Normalized crop box (x1,y1,x2,y2) and custom text coordinates
.\.venv\Scripts\python.exe make_sticker.py "path\to\photo.jpg" --person "Minju" --text "拍照存證" --crop 0.27,0.014,0.83,1.0 --aspect 1:1 --text-xy 0.5,0.88 --style yellow
```

### Batch Processing (`make_batch.py`)

Create a JSON manifest (`jobs.json`). Each entry may specify `group` and `person` to automatically route outputs to `<default_output_dir>/<group>/<person>/<person>_<text>.png`, or specify `out_dir` directly. If `crop` is omitted, `make_batch.py` automatically strips uniform white/black borders and computes a `1:1` crop biased by `y_bias`, `x_bias`, and `zoom`.

```json
[
  {
    "input": "path/to/ILLIT_Minju_01.jpg",
    "group": "ILLIT",
    "person": "Minju",
    "text": "吃瓜中",
    "y_bias": 0.12
  },
  {
    "input": "path/to/ILLIT_Wonhee_01.jpg",
    "group": "ILLIT",
    "person": "Wonhee",
    "text": "人家不管",
    "crop": [0.0, 0.09, 0.86, 0.735]
  }
]
```

Run the batch job and generate a visual verification sheet:

```powershell
.\.venv\Scripts\python.exe make_batch.py jobs.json --verify-sheet verify.jpg --json
```
