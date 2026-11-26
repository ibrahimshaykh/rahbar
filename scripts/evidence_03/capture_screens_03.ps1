# Runs one appendix script (SS-A..SS-F) live in THIS console window and saves PNG captures of
# this window only (PrintWindow), one per screenful, from the typed command to the END banner.
#   Start-Process conhost.exe -ArgumentList 'powershell -NoProfile -ExecutionPolicy Bypass -File
#     scripts\evidence_03\capture_screens_03.ps1 -Script SS-B_suite_03.sh'
param([Parameter(Mandatory = $true)][string]$Script)

$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..\..")
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win03 {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
}
"@

[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8
$ui = $Host.UI.RawUI
$ui.WindowTitle = "RAHBAR $Script"
$ui.BufferSize = New-Object System.Management.Automation.Host.Size(160, 3000)
$max = $ui.MaxPhysicalWindowSize
$w = [Math]::Min(160, $max.Width)
$h = $max.Height - 3
$ui.WindowSize = New-Object System.Management.Automation.Host.Size($w, $h)
$hwnd = [Win03]::GetConsoleWindow()
Clear-Host

Write-Host "PS $(Get-Location)> bash scripts/evidence_03/$Script"
& "C:\Program Files\Git\bin\bash.exe" "scripts/evidence_03/$Script" | ForEach-Object { Write-Host $_ }
Write-Host "PS $(Get-Location)>"
Start-Sleep -Seconds 2

$last = $ui.CursorPosition.Y
$base = "docs/evidence_03/" + ($Script -replace "\.sh$", "")
Remove-Item "$base*.png" -ErrorAction SilentlyContinue
$page = 1
$top = 0
while ($true) {
    $maxTop = [Math]::Max(0, $last - $h + 1)
    $y = [Math]::Min($top, $maxTop)
    [void][Win03]::ShowWindow($hwnd, 9)   # restore if it was minimised
    $ui.WindowPosition = New-Object System.Management.Automation.Host.Coordinates(0, $y)
    Start-Sleep -Milliseconds 900
    $r = New-Object Win03+RECT
    [void][Win03]::GetWindowRect($hwnd, [ref]$r)
    $bmp = New-Object System.Drawing.Bitmap(($r.R - $r.L), ($r.B - $r.T))
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $dc = $g.GetHdc()
    [void][Win03]::PrintWindow($hwnd, $dc, 2)
    $g.ReleaseHdc($dc)
    $name = if ($page -eq 1) { "$base.png" } else { "${base}_p$page.png" }
    $bmp.Save((Join-Path (Get-Location) $name), [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    if ($y -ge $maxTop) { break }
    $top = $y + $h - 2
    $page++
}
"pages=$page" | Out-File -Encoding ascii "$base.captured"
