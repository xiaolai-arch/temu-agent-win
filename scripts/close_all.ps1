# Close ALL msedge #32770 dialogs (pickers + alerts) for a clean slate
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class W5 {
  public delegate bool EnumProc(IntPtr h, IntPtr lp);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr lp);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr PostMessageW(IntPtr h, uint msg, IntPtr w, IntPtr l);
}
"@
$edgePids = @(); try { $edgePids = (Get-Process msedge).Id } catch { Write-Output 'NO_EDGE'; exit 0 }
$n = 0
$cb = [W5+EnumProc]{
  param($h,$lp)
  if (-not [W5]::IsWindowVisible($h)) { return $true }
  $sb = New-Object System.Text.StringBuilder 64
  [void][W5]::GetClassNameW($h, $sb, 64)
  if ($sb.ToString() -ne '#32770') { return $true }
  $p = 0; [void][W5]::GetWindowThreadProcessId($h, [ref]$p)
  if ($edgePids -notcontains $p) { return $true }
  [void][W5]::PostMessageW($h, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)  # WM_CLOSE
  $script:n++
  return $true
}
[void][W5]::EnumWindows($cb, [IntPtr]::Zero)
Write-Output ('CLOSED=' + $script:n)
