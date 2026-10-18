param([Parameter(Mandatory=$true)][string]$TargetPath)

Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class W6 {
  public delegate bool EnumProc(IntPtr h, IntPtr lp);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr lp);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr lp);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessageW(IntPtr h, uint msg, IntPtr w, string l);
  [DllImport("user32.dll")] public static extern IntPtr SendMessageW(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
"@

function ClsOf([IntPtr]$h) { $sb = New-Object System.Text.StringBuilder 64; [void][W6]::GetClassNameW($h, $sb, 64); return $sb.ToString() }
function TxtOf([IntPtr]$h) { $sb = New-Object System.Text.StringBuilder 512; [void][W6]::GetWindowTextW($h, $sb, 512); return $sb.ToString() }
function Get-ChromeDialogs {
  $edgePids = @(); try { $edgePids = (Get-Process chrome -ErrorAction Stop).Id } catch { return @() }
  $script:found = New-Object System.Collections.ArrayList
  $cb = [W6+EnumProc]{
    param($h,$lp)
    if (-not [W6]::IsWindowVisible($h)) { return $true }
    $sb = New-Object System.Text.StringBuilder 64
    [void][W6]::GetClassNameW($h, $sb, 64)
    if ($sb.ToString() -ne '#32770') { return $true }
    $p = 0; [void][W6]::GetWindowThreadProcessId($h, [ref]$p)
    if ($edgePids -contains $p) { [void]$script:found.Add($h) }
    return $true
  }
  [void][W6]::EnumWindows($cb, [IntPtr]::Zero)
  return @($script:found)
}

# wait for exactly one dialog, then let the shell view settle before touching it
$deadline = (Get-Date).AddSeconds(20)
$dlg = [IntPtr]::Zero
while ((Get-Date) -lt $deadline) {
  $ds = Get-ChromeDialogs
  if ($ds.Count -eq 1) { $dlg = $ds[0]; break }
  if ($ds.Count -gt 1) { Write-Output ('MULTI_DIALOG=' + $ds.Count); exit 3 }
  Start-Sleep -Milliseconds 300
}
if ($dlg -eq [IntPtr]::Zero) { Write-Output 'DIALOG_NOT_FOUND'; exit 1 }
Write-Output ('DIALOG=0x' + $dlg.ToString('X') + ' title="' + (TxtOf $dlg) + '"')
Start-Sleep -Milliseconds 1200   # let async shell view finish (prevents text reset race)

# children
$script:all = New-Object System.Collections.ArrayList
$cbC = [W6+EnumProc]{ param($h,$lp); [void]$script:all.Add($h); return $true }
[void][W6]::EnumChildWindows($dlg, $cbC, [IntPtr]::Zero)

# target = visible Edit with control id 1152 (the "folder:" box) — PROVEN commit path
$editH = [IntPtr]::Zero
foreach ($h in $script:all) {
  if ((ClsOf $h) -eq 'Edit' -and [W6]::GetDlgCtrlID($h) -eq 1152 -and [W6]::IsWindowVisible($h)) { $editH = $h; break }
}
if ($editH -eq [IntPtr]::Zero) {
  # fallback: bottom-most visible Edit whose rect is below dialog middle
  $dR = New-Object W6+RECT; [void][W6]::GetWindowRect($dlg, [ref]$dR)
  $mid = ($dR.T + $dR.B) / 2
  $best = -2147483648
  foreach ($h in $script:all) {
    if ((ClsOf $h) -eq 'Edit' -and [W6]::IsWindowVisible($h)) {
      $r = New-Object W6+RECT; [void][W6]::GetWindowRect($h, [ref]$r)
      if ($r.T -gt $mid -and $r.T -gt $best) { $best = $r.T; $editH = $h }
    }
  }
}
if ($editH -eq [IntPtr]::Zero) { Write-Output 'NO_EDIT_FOUND'; exit 1 }
Write-Output ('EDIT id=' + [W6]::GetDlgCtrlID($editH) + ' hwnd=0x' + $editH.ToString('X'))

# set path (programmatic set works even with ES_READONLY; sticks — verified visually)
$ret = [W6]::SendMessageW($editH, 0x000C, [IntPtr]::Zero, $TargetPath)
Write-Output ('SET ret=' + $ret)
Start-Sleep -Milliseconds 400

# commit button: control id 1 (select folder)
$btn = [IntPtr]::Zero
foreach ($h in $script:all) {
  if ((ClsOf $h) -eq 'Button' -and [W6]::GetDlgCtrlID($h) -eq 1 -and [W6]::IsWindowVisible($h)) { $btn = $h; break }
}
if ($btn -eq [IntPtr]::Zero) { Write-Output 'NO_BUTTON_FOUND'; exit 1 }
Write-Output ('BTN id=1 hwnd=0x' + $btn.ToString('X'))

# verify the button still belongs to the same dialog, then click
for ($i = 0; $i -lt 3; $i++) {
  [void][W6]::SendMessageW($btn, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero)  # BM_CLICK
  Start-Sleep -Milliseconds 1000
  $ds = Get-ChromeDialogs
  $stillMine = $false
  foreach ($d in $ds) { if ($d -eq $dlg) { $stillMine = $true } }
  if (-not $stillMine) { Write-Output 'DIALOG_CLOSED_OK'; exit 0 }
  # same dialog still open: re-set text (something cleared it) and click again
  Write-Output ('retry ' + ($i+1))
  [void][W6]::SendMessageW($editH, 0x000C, [IntPtr]::Zero, $TargetPath)
  Start-Sleep -Milliseconds 400
}
$ds = Get-ChromeDialogs
$stillMine = $false
foreach ($d in $ds) { if ($d -eq $dlg) { $stillMine = $true } }
if (-not $stillMine) { Write-Output 'DIALOG_CLOSED_OK'; exit 0 }
Write-Output 'DIALOG_STILL_OPEN'
exit 2
