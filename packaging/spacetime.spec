# PyInstaller spec: run from the repository root with
#   pyinstaller packaging/spacetime.spec
from pathlib import Path
import sys

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    datas=[
        (str(root / "scenarios"), "scenarios"),
        (str(root / "README.md"), "."),
        (str(root / "spacetime" / "resources"), "spacetime/resources"),
    ],
    hiddenimports=["PySide6"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="Spacetime", debug=False, strip=False, upx=True,
    console=False,
)
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Spacetime.app",
        bundle_identifier="org.spacetime.simulator",
    )
