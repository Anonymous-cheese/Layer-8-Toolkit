# Build and release guide

Layer 8 Toolkit 1.1.1 is a portable, one-file Windows EXE. It is not code-signed and does not auto-update. End users need no Python installation or separate data download.

## Build

Install the build dependencies on Windows, then run the release script from the repository root:

```powershell
python -m pip install -r requirements-build.txt
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1
```

The script runs unit tests and a compile check, packages the app, copies it to `dist\Layer8Toolkit.exe`, and prints its SHA-256 checksum. Each GitHub release retains its own copy of that filename, while the release title and in-app title show the version. The EXE bundles the QR library, licenses, offline OUI database, and IANA port-registry snapshot.

## Team validation

Test the packaged app on representative Windows 10/11 PCs, including high-DPI displays and keyboard navigation. Check light/dark themes, MAC-only data, two-router correlation, input warnings, session open/save, CSV/Excel sorting and filters, search by port number and use, and Wi-Fi QR scanning/export on personal and open test networks while disconnected from the internet. For Site Planner, check exact-fit and growth-sized blocks, VLAN alignment, copy, and CSV export. Confirm the title bar shows the release version.

Record the EXE checksum in release notes. Publish only the source and approved executable; do not upload session files or internal device output. Release 1.0.0 remains available for rollback. Before broad distribution, pilot with a small team and decide with IT whether a portable EXE or an organization-signed installer is appropriate. This repository does not contain a signing certificate and must not claim a build is signed.

## Updates and user data

Users update by replacing the EXE. On first run, Toolkit copies any existing `%LOCALAPPDATA%\SwitchPort Resolver\settings.json` into its own `%LOCALAPPDATA%\Layer 8 Toolkit\settings.json`; later changes do not affect the old app. Toolkit logs are under `%LOCALAPPDATA%\Layer 8 Toolkit\Logs`. Settings contain no raw device output. Explicit `.sprsession` files do contain raw switch/router text and should follow the team's data-handling rules.
