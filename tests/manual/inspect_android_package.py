"""Independent exact packaged inventory, including Chaquopy .imy archives."""
import argparse
import hashlib
import json
import re
import struct
from email.parser import Parser
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile


def load_alignments(data):
    if data[:4] != b"\x7fELF" or data[5] != 1:
        raise ValueError("Unsupported native binary")
    if data[4] == 2:
        offset = struct.unpack_from("<Q", data, 32)[0]
        entry_size, count = struct.unpack_from("<HH", data, 54)
        layout = "<IIQQQQQQ"
    elif data[4] == 1:
        offset = struct.unpack_from("<I", data, 28)[0]
        entry_size, count = struct.unpack_from("<HH", data, 42)
        layout = "<IIIIIIII"
    else:
        raise ValueError("Unsupported ELF class")
    alignments = [
        struct.unpack_from(layout, data, offset + index * entry_size)[-1]
        for index in range(count)
        if struct.unpack_from(layout, data, offset + index * entry_size)[0] == 1
    ]
    if not alignments:
        raise ValueError("No loadable native segments")
    return alignments


def inspect(data, prefix="", outer=False):
    files, distributions, natives, archives = [], [], [], []
    with ZipFile(BytesIO(data)) as package:
        for item in package.infolist():
            name = prefix + item.filename
            files.append(name)
            if item.filename.endswith((".imy", ".zip")) and "chaquopy" in item.filename:
                archives.append(name)
                children = inspect(package.read(item), name + "!")
                files.extend(children[0])
                distributions.extend(children[1])
                natives.extend(children[2])
                archives.extend(children[3])
            elif item.filename.endswith(".dist-info/METADATA"):
                metadata = Parser().parsestr(package.read(item).decode("utf-8"))
                distributions.append({
                    "path": name, "name": metadata["Name"],
                    "version": metadata["Version"],
                    "requires_python": metadata["Requires-Python"],
                    "requires_dist": metadata.get_all("Requires-Dist", []),
                })
            elif item.filename.endswith(".so"):
                alignments = load_alignments(package.read(item))
                zip_aligned = None
                if outer and item.filename.startswith("lib/") and item.compress_type == ZIP_STORED:
                    name_size, extra_size = struct.unpack_from("<HH", data, item.header_offset + 26)
                    start = item.header_offset + 30 + name_size + extra_size
                    zip_aligned = start % 16384 == 0
                natives.append({
                    "path": name, "minimum_elf_alignment": min(alignments),
                    "elf_16kb": all(value >= 16384 for value in alignments),
                    "zip_16kb": zip_aligned,
                })
    return files, distributions, natives, archives


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = args.artifact.read_bytes()
    files, distributions, natives, archives = inspect(data, outer=True)
    related = [name for name in files if re.search(
        r"(?:^|[!/])(?:PIL/|pillow[-_/])|freetype|libjpeg", name, re.I
    )]
    pins = sorted({(item["name"], item["version"]) for item in distributions})
    report = {
        "artifact": str(args.artifact.resolve()),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data), "archives": archives,
        "packaged_files": files,
        "bootstrap_sha256": hashlib.sha256(ZipFile(BytesIO(data)).read('assets/chaquopy/bootstrap.imy')).hexdigest(),
        "distributions": distributions, "pillow_related_files": related,
        "native_libraries_checked": len(natives),
        "native_failures": [item for item in natives if not item["elf_16kb"] or item["zip_16kb"] is False],
        "native_checks": natives,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".requirements.txt").write_text(
        "".join(f"{name}=={version}\n" for name, version in pins), encoding="utf-8"
    )
    print(json.dumps({
        "artifact": args.artifact.name, "sha256": report["sha256"],
        "pins": pins, "pillow_related_files_count": len(related),
        "native_libraries_checked": len(natives),
        "native_failures": report["native_failures"],
    }, indent=2))


if __name__ == "__main__":
    main()
