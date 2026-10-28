$word=New-Object -ComObject Word.Application
$word.Visible=$false
$word.DisplayAlerts=0
foreach($pattern in @('03*.docx','02*.docx')){
  $f=Get-ChildItem (Join-Path (Resolve-Path 'docs\copyright') $pattern) | Select-Object -First 1
  $doc=$word.Documents.Open($f.FullName,$false,$true)
  $pages=$doc.ComputeStatistics(2)
  Write-Output "DOC $($f.Name) PAGES $pages"
  for($i=1;$i -le $pages;$i++){
    $a=$doc.GoTo(1,1,$i).Start
    if($i -lt $pages){$b=$doc.GoTo(1,1,$i+1).Start}else{$b=$doc.Content.End}
    $text=$doc.Range($a,$b).Text
    $para=@($text -split "`r" | Where-Object { $_.Trim().Length -gt 0 })
    $sourceRows=@($para | Where-Object { $_ -notmatch '^//.*' }).Count
    Write-Output ("PAGE {0} nonempty={1} nonheader={2} chars={3}" -f $i,$para.Count,$sourceRows,$text.Length)
  }
  $doc.Close(0)
}
$word.Quit()
