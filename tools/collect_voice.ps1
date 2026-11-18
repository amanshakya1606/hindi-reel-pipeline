# Move "Generated Audio*.wav" files from $env:USERPROFILE\Downloads (oldest first) into <reel-dir>\vo-lumi\scene-NN.wav
# Usage: powershell -File tools\collect_voice.ps1 <reel-dir> [startIndex]
param([string]$ReelDir, [int]$Start = 1)
$dst = Join-Path $ReelDir 'vo-lumi'
New-Item -ItemType Directory -Force $dst | Out-Null
$i = $Start
$prev = $null
Get-ChildItem '$env:USERPROFILE\Downloads' -Filter 'Generated Audio*.wav' | Sort-Object LastWriteTime | ForEach-Object {
    $hash = (Get-FileHash $_.FullName -Algorithm MD5).Hash
    $name = 'scene-{0:D2}.wav' -f $i
    Move-Item $_.FullName -Destination (Join-Path $dst $name) -Force
    $dup = if ($hash -eq $prev) { 'DUPLICATE OF PREVIOUS' } else { '' }
    Write-Output ("{0}  {1} bytes  {2}" -f $name, (Get-Item (Join-Path $dst $name)).Length, $dup)
    $prev = $hash
    $i++
}
