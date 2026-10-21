$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $repo
try {
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; preview build stopped.' }

    python -m py_compile oui_offline.pyw resolver_workflow.py network_tools.py tools_ui.py app_preferences.py port_reference.py wifi_qr.py dns_helper.py mtu_helper.py dhcp_option121.py
    if ($LASTEXITCODE -ne 0) { throw 'Compile check failed; preview build stopped.' }

    python -m PyInstaller --clean --noconfirm --distpath dist-toolkit-preview --workpath build-toolkit-preview 'Layer 8 Toolkit.spec'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

    $exe = Join-Path $repo 'dist-toolkit-preview\Layer 8 Toolkit.exe'
    if (-not (Test-Path -LiteralPath $exe)) { throw 'Preview executable was not created.' }
    Get-FileHash -LiteralPath $exe -Algorithm SHA256 | Format-List Path, Hash
}
finally {
    Pop-Location
}
