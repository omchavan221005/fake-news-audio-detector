# run_program_and_log.ps1
# Starts FastAPI backend and Vite frontend, logging all output to run_log.txt

$logFile = Join-Path $PSScriptRoot "run_log.txt"
# Clear any existing log
Set-Content -Path $logFile -Value "" -Encoding utf8

# Start backend server
Start-Job -ScriptBlock {
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 *>> "$using:logFile" 2>&1
} | Out-Null

# Start frontend server
Start-Job -ScriptBlock {
    npx vite --host 0.0.0.0 --port 5173 *>> "$using:logFile" 2>&1
} | Out-Null

Write-Host "Backend and frontend started; logs are being written to $logFile"
