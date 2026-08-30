import json

import pytest

from library_cli import Library, LibraryError, main


def test_book_is_saved_and_visible_after_restart(tmp_path):
    path = tmp_path / "library.json"
    library = Library(path)
    library.add_book("B-001", "River", 1)

    restarted = Library(path)

    assert restarted.show_book("B-001")["title"] == "River"


def test_duplicate_book_does_not_overwrite_first_record(tmp_path):
    path = tmp_path / "library.json"
    library = Library(path)
    library.add_book("B-001", "River", 1)

    with pytest.raises(ValueError, match="duplicate book ID"):
        library.add_book("B-001", "Different Title", 5)

    restarted = Library(path)
    assert restarted.show_book("B-001")["title"] == "River"
    assert restarted.show_book("B-001")["total_copies"] == 1


def test_loan_and_return_change_availability(tmp_path):
    path = tmp_path / "library.json"
    library = Library(path)
    library.add_book("B-001", "River", 1)
    library.create_loan("L-001", "B-001")

    assert library.show_book("B-001")["available_copies"] == 0

    library.return_loan("L-001")

    assert library.show_book("B-001")["available_copies"] == 1


def test_second_loan_is_rejected_when_book_is_unavailable(tmp_path):
    library = Library(tmp_path / "library.json")
    library.add_book("B-001", "River", 1)
    library.create_loan("L-001", "B-001")

    with pytest.raises(ValueError, match="book unavailable"):
        library.create_loan("L-002", "B-001")


def test_corrupt_file_is_not_overwritten(tmp_path):
    path = tmp_path / "library.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(LibraryError, match="invalid or corrupt library file"):
        Library(path)

    assert path.read_text(encoding="utf-8") == "not json"


def test_missing_file_starts_empty_library(tmp_path):
    library = Library(tmp_path / "library.json")

    assert library.list_books() == []
    assert library.loans == {}


def test_help_lists_commands_and_examples(capsys):
    assert main(["--help"]) == 0

    output = capsys.readouterr().out
    assert "add-book" in output
    assert "list-books" in output
    assert "create-loan" in output
    assert "return-loan" in output
    assert "show-book" in output
    assert "Examples:" in output


def test_saved_file_is_json(tmp_path):
    path = tmp_path / "library.json"
    Library(path).add_book("B-001", "River", 1)

    document = json.loads(path.read_text(encoding="utf-8"))

    assert document["books"]["B-001"]["available_copies"] == 1
