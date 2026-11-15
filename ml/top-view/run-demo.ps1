param(
    [string]$Source = 'C:\Users\fbook\Downloads\13277315-uhd_3840_2160_25fps.mp4',
    [string]$Output = (Join-Path $PSScriptRoot 'outputs\cows-demo.mp4'),
    [string]$Python = (Join-Path $PSScriptRoot '..\..\..\.cow-vision-venv\Scripts\python.exe')
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) {
    throw 'Python environment not found. Pass -Python with your Python executable after installing ml/top-view/requirements.txt.'
}
& $Python (Join-Path $PSScriptRoot 'cow_segment.py') $Source --output $Output --masks
if ($LASTEXITCODE -ne 0) { throw 'Segmentation failed; inspect the output logs.' }
& $Python (Join-Path $PSScriptRoot 'validate_output.py') $Output
if ($LASTEXITCODE -ne 0) { throw 'Output validation failed.' }
Write-Output "Annotated video: $Output"
