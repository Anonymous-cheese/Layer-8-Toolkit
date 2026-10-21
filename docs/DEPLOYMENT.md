# Internal preview and release guide

This repository builds a Windows one-file executable with PyInstaller. Version `4.1.0` is a portable release build. It is not code-signed and does not auto-update.

For a local preview, install build requirements once with `python -m pip install -r requirements-build.txt`, close any running preview EXE, and run `powershell -ExecutionPolicy Bypass -File scripts\build_preview.ps1`. The script runs tests and a compile check before creating `dist-toolkit-preview\Layer 8 Toolkit.exe`, then prints its SHA-256 checksum. The EXE includes the QR library, license notices, and an IANA port-registry snapshot; users do not install dependencies or fetch data.

## Before a team release

1. Run `python -m unittest discover -s tests -v` and `python -m py_compile oui_offline.pyw resolver_workflow.py network_tools.py tools_ui.py app_preferences.py`.
2. Test the packaged app on representative Windows 10/11 PCs, including high-DPI displays, keyboard navigation, light/dark themes, MAC-only data, two-router correlation, import warnings, session open/save, CSV/Excel export, search for both `53` and `remote desktop`, and Wi-Fi QR scanning, PNG/SVG export, and image copy from personal/open test networks while disconnected from the internet.
3. Set a non-preview version in `oui_offline.pyw`, update README/changelog, and build from a clean commit with `python -m PyInstaller --clean --noconfirm "Layer 8 Toolkit.spec"`.
4. Record the SHA-256 checksum of the EXE (`Get-FileHash "dist\Layer 8 Toolkit.exe" -Algorithm SHA256`) and include it with the release notes. Keep prior releases available for rollback.
5. Decide with IT whether to distribute the portable EXE, package it as a signed installer/MSIX, or deploy through an existing device-management system. Code signing requires an organization-approved certificate; this repository does **not** have one and must not claim that a build is signed.
6. Publish a versioned GitHub release only after testing and approval. Include changes, known limitations, checksum, minimum supported Windows version, and upgrade/rollback instructions. Do not upload session files or internal device output.

## Update behavior and user data

The app currently has **no automatic update mechanism**. Users replace the EXE with an approved newer version. On first run, Toolkit copies any existing `%LOCALAPPDATA%\SwitchPort Resolver\settings.json` into its own `%LOCALAPPDATA%\Layer 8 Toolkit\settings.json`; later changes do not affect the old app. Session files remain wherever the user explicitly saved them. Toolkit logs are under `%LOCALAPPDATA%\Layer 8 Toolkit\Logs`.

Settings contain no raw device output. `.sprsession` files do contain raw switch/router text and should follow the team's data-handling rules. A release should be piloted with a small group before broad deployment.
