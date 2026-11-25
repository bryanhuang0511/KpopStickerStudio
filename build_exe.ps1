$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root ".venv\Scripts\python.exe"
$ico = Join-Path $root "launcher\app.ico"
$src = Join-Path $root "launcher\Program.cs"
$outExe = Join-Path $root "KpopStickerStudio.exe"
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if (-not (Test-Path $csc)) {
    throw "找不到 Windows 內建 C# 編譯器：$csc"
}

# 1. 使用專案 Pillow 產生專屬貼圖圖示 (app.ico)
& $py -c @"
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

size = 256
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 粉紫漸層圓角底板
for y in range(size):
    t = y / (size - 1)
    r = int(255 * (1 - t) + 124 * t)
    g = int(91 * (1 - t) + 58 * t)
    b = int(153 * (1 - t) + 237 * t)
    draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

mask = Image.new('L', (size, size), 0)
ImageDraw.Draw(mask).rounded_rectangle((10, 10, size - 11, size - 11), radius=56, fill=255)
img.putalpha(mask)

# 貼圖白邊折角造型
sticker = ImageDraw.Draw(img)
sticker.rounded_rectangle((46, 46, 210, 210), radius=34, fill=(255, 255, 255, 245))
sticker.rounded_rectangle((58, 58, 198, 198), radius=26, fill=(22, 25, 34, 255))

# 中央「貼」字
try:
    font = ImageFont.truetype(r'C:\Windows\Fonts\NotoSansTC-VF.ttf', 102)
    font.set_variation_by_axes([800])
except Exception:
    font = ImageFont.truetype(r'C:\Windows\Fonts\msjhbd.ttc', 102)

bbox = sticker.textbbox((0, 0), '貼', font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
sticker.text(((size - tw) // 2 - bbox[0], (size - th) // 2 - bbox[1] - 4), '貼', font=font, fill=(255, 115, 170, 255))

out = Path(r'$ico')
img.save(out, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print('Icon generated:', out)
"@

# 2. 編譯原生無黑窗 WinExe
& $csc /nologo /target:winexe /optimize+ /win32icon:"$ico" /r:System.Windows.Forms.dll /out:"$outExe" "$src"

Write-Host "✅ 已編譯完成：$outExe"
Get-Item $outExe | Select-Object Name, @{N='SizeKB';E={[math]::Round($_.Length/1KB,1)}}, LastWriteTime
