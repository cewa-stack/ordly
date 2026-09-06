# Sklada `icon.ico` z `icon.png` (16/32/48/256 px).
#
# UWAGA: `icon.ico` w repozytorium pochodzi z gotowego pliku
# `ordly_app_icon.ico` (Ordi z podkladka, 6 wrzesnia 2026) i ma OSIEM
# rozmiarow - lacznie z 24, 64, 96 i 128 px. `icon.png` to wyciety z niego
# obrazek 256 px, wiec ten skrypt odtworzy te sama grafike, ale w czterech
# rozmiarach zamiast osmiu. Uruchamiaj go tylko wtedy, gdy naprawde
# podmieniasz `icon.png` na nowy rysunek.

Add-Type -AssemblyName System.Drawing

$srcPath = Join-Path $PSScriptRoot "icon.png"
$outPath = Join-Path $PSScriptRoot "icon.ico"
$sizes = @(16, 32, 48, 256)

$src = [System.Drawing.Image]::FromFile($srcPath)

$pngBlobs = @()
foreach ($size in $sizes) {
    $bmp = New-Object System.Drawing.Bitmap($size, $size)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.DrawImage($src, 0, 0, $size, $size)
    $g.Dispose()

    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    $pngBlobs += ,$ms.ToArray()
    $bmp.Dispose()
    $ms.Dispose()
}
$src.Dispose()

$out = New-Object System.IO.FileStream($outPath, [System.IO.FileMode]::Create)
$bw = New-Object System.IO.BinaryWriter($out)

# ICONDIR
$bw.Write([UInt16]0)   # reserved
$bw.Write([UInt16]1)   # type: icon
$bw.Write([UInt16]$sizes.Count)

$offset = 6 + (16 * $sizes.Count)
for ($i = 0; $i -lt $sizes.Count; $i++) {
    $size = $sizes[$i]
    $blob = $pngBlobs[$i]
    $dim = if ($size -ge 256) { 0 } else { $size }
    $bw.Write([Byte]$dim)      # width
    $bw.Write([Byte]$dim)      # height
    $bw.Write([Byte]0)         # color palette
    $bw.Write([Byte]0)         # reserved
    $bw.Write([UInt16]1)       # color planes
    $bw.Write([UInt16]32)      # bits per pixel
    $bw.Write([UInt32]$blob.Length)
    $bw.Write([UInt32]$offset)
    $offset += $blob.Length
}
foreach ($blob in $pngBlobs) {
    $bw.Write($blob)
}

$bw.Flush()
$bw.Close()
$out.Close()

Write-Output "Wrote $outPath"
