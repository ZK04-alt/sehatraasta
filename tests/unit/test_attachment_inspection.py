import hashlib
import re
from pathlib import Path

import pytest

from sehatraasta.services.attachment_inspection import (
    AttachmentInspection,
    generate_attachment_stored_name,
    inspect_attachment_file,
)


def _make_pdf_sample(tmp_path, name="demo.pdf"):
    # These synthetic bytes exercise signature checks, not complete PDF parsing.
    path = tmp_path / name
    path.write_bytes(b"%PDF-1.7\nFictional club notice for testing only.\n")
    return path


def test_inspection_values(tmp_path):
    path = _make_pdf_sample(tmp_path, "Demo.PDF")
    contents = path.read_bytes()

    result = inspect_attachment_file(path)

    assert isinstance(result, AttachmentInspection)
    assert result.name == "Demo.PDF"
    assert result.extension == ".pdf"
    assert result.MIME_type == "application/pdf"
    assert result.size == len(contents)
    assert isinstance(result.size, int)
    assert result.sha == hashlib.sha256(contents).hexdigest()
    assert re.fullmatch(r"[0-9a-f]{64}", result.sha)


def test_inspection_accepts_string_path(tmp_path):
    path = _make_pdf_sample(tmp_path)
    assert inspect_attachment_file(str(path)).name == "demo.pdf"


def test_inspection_png(tmp_path):
    path = tmp_path / "Demo.PNG"
    contents = b"\x89PNG\r\n\x1a\nfictional signature test sample"
    path.write_bytes(contents)

    result = inspect_attachment_file(path)

    assert result.name == "Demo.PNG"
    assert result.extension == ".png"
    assert result.MIME_type == "image/png"
    assert result.sha == hashlib.sha256(contents).hexdigest()


def test_inspection_jpg(tmp_path):
    path = tmp_path / "demo.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0fictional signature test sample")
    assert inspect_attachment_file(path).MIME_type == "image/jpeg"


def test_inspection_jpeg(tmp_path):
    path = tmp_path / "demo.jpeg"
    path.write_bytes(b"\xff\xd8\xff\xe1fictional signature test sample")
    assert inspect_attachment_file(path).MIME_type == "image/jpeg"


def test_missing_file(tmp_path):
    with pytest.raises(ValueError, match="^attachment file not found$"):
        inspect_attachment_file(tmp_path / "missing.pdf")


def test_directory_is_not_an_attachment(tmp_path):
    directory = tmp_path / "folder.pdf"
    directory.mkdir()
    with pytest.raises(ValueError, match="^invalid attachment source$"):
        inspect_attachment_file(directory)


def test_non_path_argument():
    with pytest.raises(ValueError, match="^invalid attachment source$"):
        inspect_attachment_file(123)


def test_none_path_argument():
    with pytest.raises(ValueError, match="^invalid attachment source$"):
        inspect_attachment_file(None)


def test_empty_path_argument():
    with pytest.raises(ValueError, match="^invalid attachment source$"):
        inspect_attachment_file("")


def test_blank_path_argument():
    with pytest.raises(ValueError, match="^invalid attachment source$"):
        inspect_attachment_file("   ")


def test_null_in_path_argument():
    with pytest.raises(ValueError, match="^invalid attachment source$"):
        inspect_attachment_file("demo\x00.pdf")


def test_empty_attachment(tmp_path):
    path = tmp_path / "empty.pdf"
    path.write_bytes(b"")
    with pytest.raises(ValueError, match="^invalid file size$"):
        inspect_attachment_file(path)


def test_attachment_exactly_at_size_limit(tmp_path):
    path = tmp_path / "boundary.pdf"
    contents = b"%PDF-" + b"x" * (5242880 - 5)
    path.write_bytes(contents)

    result = inspect_attachment_file(path)

    assert result.size == 5242880
    assert result.sha == hashlib.sha256(contents).hexdigest()


def test_attachment_one_byte_above_size_limit(tmp_path):
    path = tmp_path / "too-large.pdf"
    path.write_bytes(b"%PDF-" + b"x" * (5242881 - 5))
    with pytest.raises(ValueError, match="^file too large$"):
        inspect_attachment_file(path)


def test_extension_signature_mismatch(tmp_path):
    path = tmp_path / "wrong.pdf"
    path.write_bytes(b"\x89PNG\r\n\x1a\nfictional sample")
    with pytest.raises(ValueError, match="^file type does not match extension$"):
        inspect_attachment_file(path)


def test_text_renamed_to_pdf(tmp_path):
    path = tmp_path / "pretend.pdf"
    path.write_bytes(b"This is a fictional plain text notice.")
    with pytest.raises(ValueError, match="^file type does not match extension$"):
        inspect_attachment_file(path)


def test_incomplete_signature_file(tmp_path):
    path = tmp_path / "incomplete.png"
    path.write_bytes(b"\x89PN")
    with pytest.raises(ValueError, match="^file type does not match extension$"):
        inspect_attachment_file(path)


def test_unsupported_file_extension(tmp_path):
    path = _make_pdf_sample(tmp_path, "demo.pdf.exe")
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        inspect_attachment_file(path)


def test_filename_without_extension(tmp_path):
    path = _make_pdf_sample(tmp_path, "demo")
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        inspect_attachment_file(path)


def test_filename_length_validation_is_reused(tmp_path):
    path = _make_pdf_sample(tmp_path, "a" * 147 + ".pdf")
    with pytest.raises(ValueError, match="^invalid attachment filename$"):
        inspect_attachment_file(path)


def test_original_unicode_filename_is_preserved(tmp_path):
    path = _make_pdf_sample(tmp_path, "\u0130-demo.PDF")
    assert inspect_attachment_file(path).name == "\u0130-demo.PDF"


def test_hash_covers_multiple_chunks_and_header(tmp_path):
    path = tmp_path / "several-chunks.pdf"
    contents = b"%PDF-1.7\n" + b"fictional data " * 1000 + b"final partial chunk"
    path.write_bytes(contents)

    result = inspect_attachment_file(path)

    assert result.size == len(contents)
    assert result.sha == hashlib.sha256(contents).hexdigest()
    assert result.sha != hashlib.sha256(contents[8:]).hexdigest()


def test_same_contents_different_names(tmp_path):
    first = _make_pdf_sample(tmp_path, "first.pdf")
    second = _make_pdf_sample(tmp_path, "second.pdf")
    assert inspect_attachment_file(first).sha == inspect_attachment_file(second).sha


def test_changed_contents_change_digest(tmp_path):
    first = _make_pdf_sample(tmp_path, "first.pdf")
    second = tmp_path / "second.pdf"
    second.write_bytes(first.read_bytes() + b"changed")
    assert inspect_attachment_file(first).sha != inspect_attachment_file(second).sha


def test_inspection_leaves_source_and_folder_unchanged(tmp_path):
    path = _make_pdf_sample(tmp_path)
    contents_before = path.read_bytes()
    files_before = list(tmp_path.iterdir())

    inspect_attachment_file(path)

    assert path.read_bytes() == contents_before
    assert list(tmp_path.iterdir()) == files_before


def test_rejection_leaves_source_and_folder_unchanged(tmp_path):
    path = tmp_path / "wrong.pdf"
    path.write_bytes(b"fictional plain text")
    contents_before = path.read_bytes()
    files_before = list(tmp_path.iterdir())

    with pytest.raises(ValueError, match="^file type does not match extension$"):
        inspect_attachment_file(path)

    assert path.read_bytes() == contents_before
    assert list(tmp_path.iterdir()) == files_before


def test_permission_failure_has_safe_message(tmp_path, monkeypatch):
    path = _make_pdf_sample(tmp_path)

    def denied_open(self, mode):
        raise PermissionError("private details must not become the user message")

    monkeypatch.setattr(Path, "open", denied_open)
    with pytest.raises(ValueError, match="^cannot read attachment file$"):
        inspect_attachment_file(path)


def test_stat_failure_has_safe_message(tmp_path, monkeypatch):
    path = _make_pdf_sample(tmp_path)

    def denied_stat(self, **kwargs):
        raise PermissionError("private source path")

    monkeypatch.setattr(Path, "stat", denied_stat)
    with pytest.raises(ValueError, match="^cannot read attachment file$"):
        inspect_attachment_file(path)


def test_disappearing_file_has_safe_message(tmp_path, monkeypatch):
    path = _make_pdf_sample(tmp_path)

    def missing_open(self, mode):
        raise FileNotFoundError("private source path")

    monkeypatch.setattr(Path, "open", missing_open)
    with pytest.raises(ValueError, match="^attachment file not found$"):
        inspect_attachment_file(path)


def test_symbolic_link_is_rejected(tmp_path, monkeypatch):
    path = _make_pdf_sample(tmp_path)

    def is_link(self):
        return True

    # Simulate a link even on Windows accounts that cannot create real links.
    monkeypatch.setattr(Path, "is_symlink", is_link)
    with pytest.raises(ValueError, match="^invalid attachment source$"):
        inspect_attachment_file(path)


def test_file_is_closed_after_success(tmp_path, monkeypatch):
    path = _make_pdf_sample(tmp_path)
    original_open = Path.open
    opened_files = []

    def track_open(self, mode):
        file = original_open(self, mode)
        opened_files.append(file)
        return file

    monkeypatch.setattr(Path, "open", track_open)
    inspect_attachment_file(path)
    assert len(opened_files) == 1
    assert opened_files[0].closed


def test_file_is_closed_after_validation_failure(tmp_path, monkeypatch):
    path = tmp_path / "wrong.pdf"
    path.write_bytes(b"fictional plain text")
    original_open = Path.open
    opened_files = []

    def track_open(self, mode):
        file = original_open(self, mode)
        opened_files.append(file)
        return file

    monkeypatch.setattr(Path, "open", track_open)
    with pytest.raises(ValueError, match="^file type does not match extension$"):
        inspect_attachment_file(path)
    assert len(opened_files) == 1
    assert opened_files[0].closed


def test_read_failure_is_safe_and_closes_file(tmp_path, monkeypatch):
    path = _make_pdf_sample(tmp_path)

    # This test double behaves like a file whose second read fails.
    class BrokenFile:
        def __init__(self):
            self.reads = 0
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, error_type, error, traceback):
            self.closed = True

        def read(self, size):
            self.reads += 1
            if self.reads == 1:
                return b"%PDF-1.7\nfictional sample"
            raise OSError("private filesystem details")

    broken_file = BrokenFile()

    def broken_open(self, mode):
        return broken_file

    monkeypatch.setattr(Path, "open", broken_open)
    with pytest.raises(ValueError, match="^cannot read attachment file$"):
        inspect_attachment_file(path)
    assert broken_file.closed


def test_size_limit_uses_read_bytes_and_stops_reading(tmp_path, monkeypatch):
    path = _make_pdf_sample(tmp_path)

    # The file looked small at stat(), but this reader supplies more bytes.
    class GrowingFile:
        def __init__(self):
            self.reads = 0
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, error_type, error, traceback):
            self.closed = True

        def read(self, size):
            assert size == 4096
            self.reads += 1
            assert self.reads <= 1281
            return b"%PDF-" + b"x" * (4096 - 5)

    growing_file = GrowingFile()

    def growing_open(self, mode):
        return growing_file

    monkeypatch.setattr(Path, "open", growing_open)
    with pytest.raises(ValueError, match="^file too large$"):
        inspect_attachment_file(path)
    assert growing_file.reads == 1281
    assert growing_file.closed


def test_generated_pdf_name():
    name = generate_attachment_stored_name(".pdf")
    assert re.fullmatch(r"[0-9a-f]{32}\.pdf", name)
    assert "/" not in name
    assert "\\" not in name


def test_generated_png_name():
    assert re.fullmatch(r"[0-9a-f]{32}\.png", generate_attachment_stored_name(".png"))


def test_generated_jpg_name():
    assert re.fullmatch(r"[0-9a-f]{32}\.jpg", generate_attachment_stored_name(".jpg"))


def test_generated_jpeg_name():
    assert re.fullmatch(r"[0-9a-f]{32}\.jpeg", generate_attachment_stored_name(".jpeg"))


def test_generated_name_unsupported_extension():
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        generate_attachment_stored_name(".exe")


def test_generated_name_non_string_extension():
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        generate_attachment_stored_name(123)


def test_generated_name_rejects_path_components():
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        generate_attachment_stored_name("../demo.pdf")


def test_generated_name_requires_normalized_extension():
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        generate_attachment_stored_name(".PDF")


def test_generation_does_not_create_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    files_before = list(tmp_path.iterdir())
    generate_attachment_stored_name(".pdf")
    assert list(tmp_path.iterdir()) == files_before
