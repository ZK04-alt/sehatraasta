from io import BytesIO
import struct
import zlib
import zipfile
import pytest


def archive_bytes(method, content):
    output=BytesIO()
    with zipfile.ZipFile(output,'w',method) as archive:
        archive.writestr('fictional.txt',content)
    return output.getvalue()


@pytest.mark.parametrize('method',[zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED,zipfile.ZIP_BZIP2,zipfile.ZIP_LZMA])
def test_checked_member_preserves_supported_compression_and_budget(method):
    from sehatraasta.services.archive_reader import read_checked_members
    content=b'Fictional safe sample\n'*24000
    with zipfile.ZipFile(BytesIO(archive_bytes(method,content))) as archive:
        assert read_checked_members(archive,archive.infolist(),len(content))=={'fictional.txt':content}
        with pytest.raises(zipfile.BadZipFile):
            read_checked_members(archive,archive.infolist(),len(content)-1)


@pytest.mark.parametrize('method',[zipfile.ZIP_BZIP2,zipfile.ZIP_LZMA])
def test_forged_small_declared_size_does_not_expand_unbounded(method):
    from sehatraasta.services.archive_reader import read_checked_members
    content=b'A'*(512*1024)
    forged=bytearray(archive_bytes(method,content))
    central=forged.index(b'PK\x01\x02')
    for offset in (22,central+24):
        struct.pack_into('<I',forged,offset,1)
    for offset in (14,central+16):
        struct.pack_into('<I',forged,offset,zlib.crc32(b'A'))
    with zipfile.ZipFile(BytesIO(forged)) as archive:
        with pytest.raises(zipfile.BadZipFile):
            read_checked_members(archive,archive.infolist(),512*1024)


def test_crc_failure_and_truncation_remain_rejected():
    from sehatraasta.services.archive_reader import read_checked_members
    content=bytearray(archive_bytes(zipfile.ZIP_STORED,b'Fictional original'))
    content[30+len('fictional.txt')]^=1
    with zipfile.ZipFile(BytesIO(content)) as archive:
        with pytest.raises(zipfile.BadZipFile):
            read_checked_members(archive,archive.infolist(),1000)
    with pytest.raises(zipfile.BadZipFile):
        zipfile.ZipFile(BytesIO(content[:-15]))


@pytest.mark.parametrize('method',[zipfile.ZIP_BZIP2,zipfile.ZIP_LZMA])
def test_inner_decoder_call_is_bounded_before_outer_read(method):
    from sehatraasta.services.archive_reader import bound_member
    with zipfile.ZipFile(BytesIO(archive_bytes(method,b'A'*(512*1024)))) as archive:
        with archive.open('fictional.txt') as member:
            bound_member(member,method)
            assert len(member._read1(1))<=member.MIN_READ_SIZE
