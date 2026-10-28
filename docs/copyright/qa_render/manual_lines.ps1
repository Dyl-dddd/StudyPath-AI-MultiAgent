$word=New-Object -ComObject Word.Application
$word.Visible=$false
$word.DisplayAlerts=0
$f=Get-ChildItem (Join-Path (Resolve-Path 'docs\copyright') '02_*.docx') | Where-Object { $_.BaseName -notmatch '草案' } | Select-Object -First 1
$doc=$word.Documents.Open($f.FullName,$false,$true)
$pages=$doc.ComputeStatistics(2)
for($i=1;$i -le $pages;$i++){
  $a=$doc.GoTo(1,1,$i).Start
  if($i -lt $pages){$b=$doc.GoTo(1,1,$i+1).Start}else{$b=$doc.Content.End}
  $r=$doc.Range($a,$b)
  Write-Output ("page={0} paragraphs={1} lines={2}" -f $i,$r.ComputeStatistics(4),$r.ComputeStatistics(1))
}
$doc.Close(0)
$word.Quit()
