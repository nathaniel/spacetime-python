"""Read and write Java-style scenario property files."""

from pathlib import Path
import re


def _unescape_java(value: str) -> str:
    """Decode Unicode escapes used by Java properties files."""
    return re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda match: chr(int(match.group(1), 16)),
        value,
    )


def read_properties(path: Path) -> dict[str,str]:
    """Read non-comment key-value pairs from a properties file."""
    result={}
    for line in path.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith(("#","!")): continue
        key, sep, value=line.partition("=")
        if not sep: key, sep, value=line.partition(":")
        if sep:
            result[_unescape_java(key.strip())] = _unescape_java(value.strip())
    return result
def write_properties(path: Path, values: dict[str,str]) -> None:
    """Write key-value pairs in the scenario properties format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines=["# This is a scenario file for the program JAVA SPACETIME."]
    lines += [f"{k}={v}" for k,v in sorted(values.items())]
    path.write_text("\n".join(lines)+"\n", encoding="utf-8")
