# Leest datums van alle bestanden in de mappen uit data\zonderjaar.txt via de Windows Shell
# (werkt ook voor OneDrive-bestanden die alleen online staan, zonder te downloaden).
# Uitvoer: data\datums.tsv  (werkpad, relatief pad, opnamedatum, media gemaakt, gewijzigd, gemaakt)
$ErrorActionPreference = 'SilentlyContinue'
$app = Split-Path $PSScriptRoot -Parent
$lijst = Get-Content (Join-Path $app 'data\zonderjaar.txt') -Encoding UTF8
$uit = New-Object System.Collections.Generic.List[string]
$sh = New-Object -ComObject Shell.Application
$ext = '\.(jpe?g|png|webp|gif|bmp|tiff?|heic|jfif|mp4|mov|avi|m4v|mkv|wmv|mpe?g|flv|webm|3gpp|vob)$'
function Schoon($s) { ($s -replace '[^\d\-: /]', '').Trim() }
foreach ($werk in $lijst) {
  if (-not (Test-Path $werk)) { continue }
  $mappen = @($werk) + @(Get-ChildItem $werk -Directory -Recurse -Depth 3 | Where-Object { $_.FullName -notmatch '\\(\.git|lib|node_modules|Library)\\' } | ForEach-Object FullName)
  foreach ($m in $mappen) {
    $fo = $sh.Namespace($m); if (-not $fo) { continue }
    foreach ($it in $fo.Items()) {
      if ($it.IsFolder -or $it.Name -notmatch $ext -and $it.Path -notmatch $ext) { continue }
      $rel = $it.Path.Substring($werk.Length).TrimStart('\')
      $uit.Add(($werk, $rel, (Schoon $fo.GetDetailsOf($it,12)), (Schoon $fo.GetDetailsOf($it,214)), (Schoon $fo.GetDetailsOf($it,3)), (Schoon $fo.GetDetailsOf($it,4))) -join "`t")
    }
  }
}
[IO.File]::WriteAllLines((Join-Path $app 'data\datums.tsv'), $uit, [Text.Encoding]::UTF8)
"regels: $($uit.Count)"
