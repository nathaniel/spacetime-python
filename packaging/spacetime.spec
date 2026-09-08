# PyInstaller spec: run from the repository root with
#   pyinstaller python/packaging/spacetime.spec
from pathlib import Path

root = Path(SPECPATH).parent.parent
a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    datas=[
        (str(root.parent / "scenarios"), "scenarios"),
        (str(root / "README.md"), "."),
    ],
    hiddenimports=["PySide6"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="Spacetime", debug=False, strip=False, upx=True,
    console=False,
)
