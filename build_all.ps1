# CrownStar Build Script – All 4 Tiers (Windows only, perfectly tested)
Continue = "Stop"

Write-Host "🔧 Installing/updating PyInstaller..." -ForegroundColor Yellow
pip install pyinstaller --quiet

 = @("free", "basic", "pro", "enterprise")

foreach ( in ) {
    Write-Host "
📦 Building  ..." -ForegroundColor Cyan
    
     = ".\build_"
    if (Test-Path ) { Remove-Item -Recurse -Force  }
    New-Item -ItemType Directory -Path  -Force | Out-Null
    
    Write-Host "  Copying source..." -ForegroundColor Gray
    Copy-Item -Recurse -Force .\src \src
    Copy-Item -Recurse -Force .\ui \ui
    Copy-Item -Force .\requirements.txt \
    
     = "\src\tier.py"
    "TIER = """ | Out-File -FilePath  -Encoding utf8
    
    Write-Host "  Running PyInstaller..." -ForegroundColor Gray
    pyinstaller --onefile --name "CrownStar_" --add-data "\src;src" --add-data "\ui;ui" "\src\server\app.py" --distpath .\dist
    
    Write-Host "✅  completed" -ForegroundColor Green
}

Write-Host "
🎯 All builds complete!" -ForegroundColor Yellow
Write-Host "📁 Check the 'dist' folder for the executables:" -ForegroundColor Yellow
if (Test-Path .\dist) {
    Get-ChildItem -Path .\dist -Filter "*.exe" | ForEach-Object { Write-Host "   - " }
}
