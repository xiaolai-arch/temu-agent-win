param([Parameter(Mandatory=$true)][string]$ImagePath)

# Windows 自带 OCR（Windows.Media.Ocr），中文优先。输出 JSON 到 stdout。
# 坐标：物理像素，相对图片左上角；格式 {text, x, y, w, h}。
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.RandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]

Function AwaitOp($WinRtTask, $ResultType) {
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
                       $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
Function AwaitAction($WinRtAction) {
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
                       $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
    $netTask = $asTask.Invoke($null, @($WinRtAction))
    $netTask.Wait(-1) | Out-Null
}

$file = AwaitOp ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream = AwaitOp ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = AwaitOp ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = AwaitOp ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

$lang = [Windows.Globalization.Language]::new('zh-CN')
$engine = if ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($lang)) {
    [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
} else {
    [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}
if ($null -eq $engine) { throw '无可用 OCR 引擎（缺中文语言包？）' }

$result = AwaitOp ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$scaleX = $decoder.PixelWidth / $bitmap.PixelWidth
$scaleY = $decoder.PixelHeight / $bitmap.PixelHeight

$lines = @()
foreach ($line in $result.Lines) {
    $xs = @($line.Words | ForEach-Object { $_.BoundingRect.X })
    $ys = @($line.Words | ForEach-Object { $_.BoundingRect.Y })
    $rs = @($line.Words | ForEach-Object { $_.BoundingRect.X + $_.BoundingRect.Width })
    $bs = @($line.Words | ForEach-Object { $_.BoundingRect.Y + $_.BoundingRect.Height })
    $minX = ($xs | Measure-Object -Minimum).Minimum
    $minY = ($ys | Measure-Object -Minimum).Minimum
    $maxR = ($rs | Measure-Object -Maximum).Maximum
    $maxB = ($bs | Measure-Object -Maximum).Maximum
    $lines += [ordered]@{
        text = $line.Text
        x = [math]::Round($minX * $scaleX)
        y = [math]::Round($minY * $scaleY)
        w = [math]::Round(($maxR - $minX) * $scaleX)
        h = [math]::Round(($maxB - $minY) * $scaleY)
    }
}

[ordered]@{ width = $decoder.PixelWidth; height = $decoder.PixelHeight; lines = $lines } |
    ConvertTo-Json -Depth 4 -Compress | Write-Output
