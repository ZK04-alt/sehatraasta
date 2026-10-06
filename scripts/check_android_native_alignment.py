"""Check all packaged native libraries, including Chaquopy's nested wheel ZIPs."""
import argparse
import json
import struct
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED


def load_alignments(data):
    if data[:4] != b'\x7fELF' or data[5] != 1:
        raise ValueError('Unsupported native binary')
    if data[4] == 2:
        offset = struct.unpack_from('<Q', data, 32)[0]
        entry_size, count = struct.unpack_from('<HH', data, 54)
        layout = '<IIQQQQQQ'
    elif data[4] == 1:
        offset = struct.unpack_from('<I', data, 28)[0]
        entry_size, count = struct.unpack_from('<HH', data, 42)
        layout = '<IIIIIIII'
    else:
        raise ValueError('Unsupported native binary')
    alignments = []
    for index in range(count):
        segment = struct.unpack_from(layout, data, offset + index * entry_size)
        if segment[0] == 1:  # PT_LOAD
            alignments.append(segment[-1])
    if not alignments:
        raise ValueError('No loadable native segments')
    return alignments


def inspect_zip(data, prefix='', check_apk_offsets=False):
    results = []
    with ZipFile(BytesIO(data)) as archive:
        for item in archive.infolist():
            if item.filename.endswith('.so'):
                content = archive.read(item)
                alignments = load_alignments(content)
                zip_aligned = None
                if check_apk_offsets and item.filename.startswith('lib/') and item.compress_type == ZIP_STORED:
                    name_size, extra_size = struct.unpack_from('<HH', data, item.header_offset + 26)
                    start = item.header_offset + 30 + name_size + extra_size
                    zip_aligned = start % 16384 == 0
                results.append(dict(path=prefix+item.filename, minimum_elf_alignment=min(alignments),
                                    elf_16kb=all(value >= 16384 for value in alignments), zip_16kb=zip_aligned))
            elif item.filename.endswith('.zip') and 'chaquopy' in item.filename:
                results.extend(inspect_zip(archive.read(item), prefix+item.filename+'!'))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('artifact', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    checks = inspect_zip(args.artifact.read_bytes(), check_apk_offsets=args.artifact.suffix=='.apk')
    failed = [item for item in checks if not item['elf_16kb'] or item['zip_16kb'] is False]
    report = dict(artifact=args.artifact.name, libraries_checked=len(checks), failed=failed,
                  passed=bool(checks) and not failed, checks=checks,
                  limitation='Static checks only. Run on a 16 KB device before release.')
    result = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result+'\n', encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('artifact','libraries_checked','passed','failed')}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
