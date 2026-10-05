"""Build RamWarden's Microsoft Store package: dist/RamWarden-<version>.msix.

The Store re-signs the package with Microsoft's certificate on upload, so it is built unsigned.
Steps: PyInstaller one-dir build (same flags as build.bat) -> stage it with Store tile images
and AppxManifest.xml -> makeappx pack.

  python tools/build_msix.py                 # full build
  python tools/build_msix.py --skip-build    # re-pack the existing dist/RamWarden
  python tools/build_msix.py --icon art.png  # tile images from another square PNG (the new logo)

makeappx comes from Microsoft's Microsoft.Windows.SDK.BuildTools NuGet package, unpacked into
tools/_buildtools (gitignored), so the full Windows SDK isn't needed.

Manifest notes:
  - Identity values are RamWarden's reservation in Partner Center (Product identity page).
  - Registry and file-system write virtualization are OFF (desktop6 + unvirtualizedResources):
    otherwise Windows redirects the Startup tab's changes (HKCU Run keys, the Startup folder)
    into a private per-app copy and they'd silently do nothing. Needs a Store justification.
  - allowElevation: the ADMIN button relaunches RamWarden elevated.
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
STAGE = ROOT / "build" / "msix"
TOOLS = ROOT / "tools" / "_buildtools"

IDENTITY_NAME = "SixthDayStudios.RamWarden"
PUBLISHER = "CN=DBF1C6F8-2733-4003-A634-FEF2E0E04CF5"
PUBLISHER_DISPLAY = "Sixth Day Studios"
DESCRIPTION = "Windows RAM and process manager"

# Same as build.bat, so the Store build and the installer build are the same program.
PYINSTALLER_ARGS = [
    "--onedir", "--windowed", "--name", "RamWarden", "--icon", "icon.ico",
    "--add-data", "icon.ico;.", "--add-data", "logo.png;.", "--add-data", "CHANGELOG.md;.",
    "--add-data", r"assets\sfx;assets\sfx", "--collect-all", "psutil",
    "--hidden-import", "psutil._pswindows", "--hidden-import", "psutil._psutil_windows",
    "--noconfirm", "main.pyw",
]

# Store tile images: name -> (width, height). Plain files, no scale qualifiers, so no PRI is needed.
TILES = {"StoreLogo.png": (50, 50), "Square44x44Logo.png": (44, 44),
         "Square150x150Logo.png": (150, 150), "Wide310x150Logo.png": (310, 150)}

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         xmlns:desktop6="http://schemas.microsoft.com/appx/manifest/desktop/windows10/6"
         IgnorableNamespaces="uap rescap desktop6">
  <Identity Name="{name}" Publisher="{publisher}" Version="{version}" ProcessorArchitecture="x64"/>
  <Properties>
    <DisplayName>RamWarden</DisplayName>
    <PublisherDisplayName>{publisher_display}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
    <desktop6:RegistryWriteVirtualization>disabled</desktop6:RegistryWriteVirtualization>
    <desktop6:FileSystemWriteVirtualization>disabled</desktop6:FileSystemWriteVirtualization>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0"/>
  </Dependencies>
  <Resources>
    <Resource Language="en-us"/>
  </Resources>
  <Applications>
    <Application Id="RamWarden" Executable="RamWarden.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="RamWarden" Description="{description}" BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png">
        <uap:DefaultTile Wide310x150Logo="Assets\\Wide310x150Logo.png"/>
      </uap:VisualElements>
    </Application>
  </Applications>
  <Capabilities>
    <rescap:Capability Name="runFullTrust"/>
    <rescap:Capability Name="allowElevation"/>
    <rescap:Capability Name="unvirtualizedResources"/>
  </Capabilities>
</Package>
"""


def app_version():
    """APP_VERSION from main.pyw as a Store version: 1.5.1 -> 1.5.1.0 (the last part must be 0)."""
    m = re.search(r'^APP_VERSION\s*=\s*"([\d.]+)"', (ROOT / "main.pyw").read_text(encoding="utf-8"), re.M)
    parts = (m.group(1).split(".") + ["0", "0"])[:3]
    return ".".join(parts + ["0"])


def makeappx():
    """Path to makeappx.exe from the unpacked BuildTools package."""
    found = sorted(TOOLS.glob("bin/*/x64/makeappx.exe"))
    if not found:
        sys.exit("makeappx.exe not found: unpack Microsoft.Windows.SDK.BuildTools (x64) into tools/_buildtools")
    return found[-1]


def tile(src, size):
    """The icon centred on a transparent canvas of `size` (wide tiles get side padding)."""
    w, h = size
    side = min(w, h)
    icon = src.resize((side, side), Image.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.paste(icon, ((w - side) // 2, (h - side) // 2), icon)
    return canvas


def main():
    """Build, stage, write the manifest, pack."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true", help="re-pack the existing dist/RamWarden")
    ap.add_argument("--icon", default=str(ROOT / "icon_preview.png"), help="square PNG for the Store tiles")
    a = ap.parse_args()

    if not a.skip_build:
        subprocess.run([sys.executable, "-m", "PyInstaller", *PYINSTALLER_ARGS], cwd=ROOT, check=True)
    app_dir = ROOT / "dist" / "RamWarden"
    if not (app_dir / "RamWarden.exe").exists():
        sys.exit("dist/RamWarden/RamWarden.exe missing: run without --skip-build")

    if STAGE.exists():
        shutil.rmtree(STAGE)
    shutil.copytree(app_dir, STAGE)
    (STAGE / "Assets").mkdir()
    src = Image.open(a.icon).convert("RGBA")
    for name, size in TILES.items():
        tile(src, size).save(STAGE / "Assets" / name)

    version = app_version()
    (STAGE / "AppxManifest.xml").write_text(MANIFEST.format(
        name=IDENTITY_NAME, publisher=PUBLISHER, publisher_display=PUBLISHER_DISPLAY,
        version=version, description=DESCRIPTION), encoding="utf-8")

    out = ROOT / "dist" / f"RamWarden-{version}.msix"
    subprocess.run([str(makeappx()), "pack", "/d", str(STAGE), "/p", str(out), "/o"], check=True)
    print(f"\nBuilt {out} ({out.stat().st_size / 1e6:.1f} MB), version {version}")


if __name__ == "__main__":
    main()
