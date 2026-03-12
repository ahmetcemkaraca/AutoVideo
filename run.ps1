#Requires -Version 5.0
<#
.SYNOPSIS
    AutoVideo PowerShell Launcher with proper terminal handling

.DESCRIPTION
    Launches AutoVideo application with clean terminal output and proper exit handling
    for PowerShell. Ensures terminal history and Ctrl+C handlers work correctly.

.PARAMETER Arguments
    Arguments to pass to the video_renderer module

.EXAMPLE
    .\run.ps1
    .\run.ps1 -Arguments "--tui"
    .\run.ps1 --batch
#>

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)

# Terminal cleanup handler
function Cleanup-Terminal {
    [Console]::Out.Flush()
    [Console]::Error.Flush()
}

# Register cleanup on exit
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    Cleanup-Terminal
}

# Trap Ctrl+C properly
$host.UI.RawUI.BackgroundColor = 'Black'
$host.UI.RawUI.ForegroundColor = 'Gray'

try {
    # Run Python launcher
    $exitCode = 0
    
    if ($Arguments.Count -gt 0) {
        # Passthrough mode with arguments
        & python run.py $Arguments
        $exitCode = $LASTEXITCODE
    } else {
        # Interactive mode
        & python run.py
        $exitCode = $LASTEXITCODE
        
        # Only pause in interactive mode if not in a pipeline
        if (-not [Console]::IsInputRedirected) {
            Write-Host ""
            Read-Host -Prompt "Devam etmek icin tuslayiniza basin"
        }
    }
    
    exit $exitCode
}
catch {
    Write-Error -Message "Hata: $_"
    exit 1
}
finally {
    Cleanup-Terminal
}
