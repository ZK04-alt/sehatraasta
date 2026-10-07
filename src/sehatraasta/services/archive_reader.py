"""Bounded ZIP members, including older Android CPython BZIP2/LZMA decoders.

Adapted from CPython 3.12.15's bounded ZipExtFile._read1 and ZIP LZMA
wrapper. Only the opened member changes; header, overlap and CRC checks
remain stdlib-owned. Do not replace with an unbounded decompress fallback.
"""
import lzma
from types import MethodType
import zipfile
import zlib

READ_CHUNK = 64 * 1024
# ZIP's ordinary LZMA writer uses 8 MiB. Preserve it, but reject hostile
# dictionary requests before liblzma allocates native memory.
MAX_LZMA_DICTIONARY = 16 * 1024 * 1024


class _BoundedLZMA:
    def __init__(self):
        self.decoder = None
        self.header = bytearray()
        self.eof = False

    @property
    def needs_input(self):
        return self.decoder is None or self.decoder.needs_input

    def decompress(self, data, max_length):
        if max_length < 0:
            raise zipfile.BadZipFile('unbounded decompression is unavailable')
        if self.decoder is None:
            self.header.extend(data)
            if len(self.header) < 4:
                return b''
            boundary = 4 + int.from_bytes(self.header[2:4], 'little')
            if len(self.header) <= boundary:
                return b''
            properties = lzma._decode_filter_properties(lzma.FILTER_LZMA1,bytes(self.header[4:boundary]))
            if properties['dict_size'] > MAX_LZMA_DICTIONARY:
                raise zipfile.BadZipFile('LZMA dictionary exceeds supported 16 MiB limit')
            self.decoder = lzma.LZMADecompressor(lzma.FORMAT_RAW,filters=[properties])
            data = bytes(self.header[boundary:])
            self.header.clear()
        result = self.decoder.decompress(data,max_length)
        self.eof = self.decoder.eof
        return result


def _bounded_read1(member, requested):
    if member._eof or requested <= 0:
        return b''
    bound = min(READ_CHUNK,max(requested,member.MIN_READ_SIZE))
    decoder = member._decompressor
    compressed = member._read2(bound) if decoder.needs_input else b''
    try:
        decoded = decoder.decompress(compressed,bound)
    except TypeError:
        raise zipfile.BadZipFile('bounded ZIP decoder unavailable') from None
    if len(decoded) > member._left:
        raise zipfile.BadZipFile('ZIP member exceeds declared size')
    member._left -= len(decoded)
    member._eof = member._left==0 or decoder.eof or (member._compress_left<=0 and decoder.needs_input)
    member._update_crc(decoded)
    return decoded


def bound_member(member, compression):
    if compression not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
        if compression==zipfile.ZIP_LZMA:
            member._decompressor = _BoundedLZMA()
        member._read1 = MethodType(_bounded_read1,member)


def read_checked_member(archive, info, limit):
    if info.file_size<0 or info.file_size>limit:
        raise zipfile.BadZipFile('ZIP member exceeds archive budget')
    output = bytearray()
    try:
        with archive.open(info) as member:
            bound_member(member,info.compress_type)
            while True:
                chunk = member.read(min(READ_CHUNK,limit-len(output)+1))
                if not chunk:
                    break
                if len(output)+len(chunk)>limit:
                    raise zipfile.BadZipFile('ZIP member exceeds archive budget')
                output.extend(chunk)
    except (EOFError,OSError,lzma.LZMAError,zlib.error):
        raise zipfile.BadZipFile('invalid compressed ZIP member') from None
    if len(output)!=info.file_size:
        raise zipfile.BadZipFile('ZIP member size mismatch')
    return bytes(output)


def read_checked_members(archive,infos,budget):
    members, remaining = {},budget
    for info in infos:
        if info.filename in members:
            raise zipfile.BadZipFile('duplicate ZIP member')
        content = read_checked_member(archive,info,remaining)
        remaining -= len(content)
        members[info.filename] = content
    return members
