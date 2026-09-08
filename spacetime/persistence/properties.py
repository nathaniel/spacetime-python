"""Read and write Java-style scenario property files."""

from pathlib import Path
def _unescape_java(value: str) -> str:
    """Decode escape sequences used by Java properties files."""
    result = []
    index = 0
    while index < len(value):
        if value[index] != "\\" or index + 1 >= len(value):
            result.append(value[index])
            index += 1
            continue
        index += 1
        escaped = value[index]
        if escaped == "n":
            result.append("\n")
        elif escaped == "r":
            result.append("\r")
        elif escaped == "t":
            result.append("\t")
        elif escaped == "f":
            result.append("\f")
        elif escaped == "u" and index + 4 < len(value):
            digits = value[index + 1 : index + 5]
            try:
                result.append(chr(int(digits, 16)))
                index += 4
            except ValueError:
                result.append("u")
        else:
            result.append(escaped)
        index += 1
    return "".join(result)


def _escape_java(value: str) -> str:
    """Encode values for Java-compatible properties files."""
    return (
        value.replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\f", "\\f")
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
    lines += [f"{k}={_escape_java(str(v))}" for k,v in sorted(values.items())]
    path.write_text("\n".join(lines)+"\n", encoding="utf-8")
