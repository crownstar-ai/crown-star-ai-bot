# =================================================================
# CrownStar Python PATH Cleaner
# 清理 用户变量 和 系统变量 中所有包含 "Python" 的 PATH 条目
# =================================================================

Write-Host "🔍 正在分析当前 PATH 中的 Python 条目..." -ForegroundColor Cyan

# 获取当前 PATH（用户变量）
 = [Environment]::GetEnvironmentVariable("Path", "User")
 = [Environment]::GetEnvironmentVariable("Path", "Machine")

# 显示当前 Python 条目
Write-Host "
📋 用户变量 PATH 中的 Python 条目:" -ForegroundColor Yellow
 -split ";" | Select-String -Pattern "Python" -CaseSensitive:False

Write-Host "
📋 系统变量 PATH 中的 Python 条目:" -ForegroundColor Yellow
 -split ";" | Select-String -Pattern "Python" -CaseSensitive:False

Write-Host "
⚠️  即将移除所有包含 'Python' 的 PATH 条目（不区分大小写）" -ForegroundColor Red

# 移除 Python 路径（用户变量）
 = ( -split ";") | Where-Object {
     -notmatch "Python"
} | Where-Object {  -ne "" } | Join-Path -Path {  } -Resolve -ErrorAction SilentlyContinue

# 移除 Python 路径（系统变量）
 = ( -split ";") | Where-Object {
     -notmatch "Python"
} | Where-Object {  -ne "" } | Join-Path -Path {  } -Resolve -ErrorAction SilentlyContinue

# 写入新的环境变量
[Environment]::SetEnvironmentVariable("Path", , "User")
[Environment]::SetEnvironmentVariable("Path", , "Machine")

Write-Host "✅ 已移除所有 Python 路径！" -ForegroundColor Green

# 显示清理后的结果
Write-Host "
✅ 清理后的用户变量 PATH:" -ForegroundColor Yellow
 -split ";" | Select-String -Pattern "Python" -CaseSensitive:False | Write-Host

Write-Host "
✅ 清理后的系统变量 PATH:" -ForegroundColor Yellow
 -split ";" | Select-String -Pattern "Python" -CaseSensitive:False | Write-Host

Write-Host "
🔄 请关闭所有 PowerShell 窗口，然后重新打开以生效。" -ForegroundColor Cyan
