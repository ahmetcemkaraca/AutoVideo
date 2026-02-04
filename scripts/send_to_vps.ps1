param(
    [string]$Ip,
    [string]$Port
)

if (-not $Ip -or -not $Port) {
    Write-Host "Usage: .\scripts\send_to_vps.ps1 <VPS_IP> <PORT>"
    exit 1
}

Write-Host "Sending to $Ip:$Port..."

# Use tar to compress and stream, pipe directly to nc
# Excludes heavy media files and build artifacts
tar -czvf - `
    --exclude "*.mp4" `
    --exclude "*.mkv" `
    --exclude "*.mov" `
    --exclude "*.avi" `
    --exclude "*.webm" `
    --exclude "*.w64" `
    --exclude "tmp" `
    --exclude "music" `
    --exclude "archive" `
    --exclude "__pycache__" `
    --exclude ".git" `
    --exclude ".vscode" `
    --exclude "venv" `
    video_renderer scripts README.md | nc $Ip $Port

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nDone."
} else {
    Write-Host "`nError. Make sure 'nc' is installed and in your PATH."
}
