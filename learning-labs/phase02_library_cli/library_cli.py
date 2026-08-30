import argparse
import json
import os
from pathlib import Path
import sys


class LibraryError(Exception):
    pass


class Library:
    def __init__(self, path):
        self.path = Path(path)
        self.books = {}
        self.loans = {}
        self.load()

    def load(self):
        if not self.path.exists():
            return

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.books = data["books"]
            self.loans = data["loans"]
            if not isinstance(self.books, dict) or not isinstance(self.loans, dict):
                raise ValueError
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise LibraryError("invalid or corrupt library file") from error

    def save(self):
        temporary = self.path.with_name(self.path.name + ".tmp")
        self.path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if self.path.exists():
                json.loads(self.path.read_text(encoding="utf-8"))

            data = {"books": self.books, "loans": self.loans}
            temporary.write_text(
                json.dumps(data, indent=2) + "\n",
                encoding="utf-8",
            )
            json.loads(temporary.read_text(encoding="utf-8"))
            os.replace(temporary, self.path)
        except (OSError, TypeError, json.JSONDecodeError) as error:
            if temporary.exists():
                temporary.unlink()
            raise LibraryError("could not safely save library file") from error

    def add_book(self, book_id, title, copies):
        if not isinstance(book_id, str) or not book_id.strip():
            raise ValueError("missing book ID")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("missing title")
        if copies <= 0:
            raise ValueError("copies must be positive")
        if book_id in self.books:
            raise ValueError("duplicate book ID")

        self.books[book_id] = {
            "ID": book_id,
            "title": title,
            "total_copies": copies,
            "available_copies": copies,
        }
        self.save()
        return self.books[book_id]

    def list_books(self):
        return list(self.books.values())

    def show_book(self, book_id):
        if book_id not in self.books:
            raise ValueError("book not found")
        return self.books[book_id]

    def create_loan(self, loan_id, book_id):
        if loan_id in self.loans:
            raise ValueError("duplicate loan ID")

        book = self.show_book(book_id)
        if book["available_copies"] == 0:
            raise ValueError("book unavailable")

        self.loans[loan_id] = {
            "ID": loan_id,
            "book_ID": book_id,
            "active": True,
        }
        book["available_copies"] -= 1
        self.save()
        return self.loans[loan_id]

    def return_loan(self, loan_id):
        if loan_id not in self.loans:
            raise ValueError("loan not found")

        loan = self.loans[loan_id]
        if not loan["active"]:
            raise ValueError("loan already returned")

        loan["active"] = False
        self.books[loan["book_ID"]]["available_copies"] += 1
        self.save()
        return loan


def build_parser():
    parser = argparse.ArgumentParser(
        description="Fictional library checkout JSON practice CLI.",
        epilog=(
            "Examples: library_cli add-book B-001 River 1; "
            "library_cli create-loan L-001 B-001"
        ),
    )
    parser.add_argument("--file", default="library.json")
    commands = parser.add_subparsers(dest="command", required=True)

    add_book = commands.add_parser("add-book")
    add_book.add_argument("book_id")
    add_book.add_argument("title")
    add_book.add_argument("copies", type=int)

    commands.add_parser("list-books")

    show_book = commands.add_parser("show-book")
    show_book.add_argument("book_id")

    create_loan = commands.add_parser("create-loan")
    create_loan.add_argument("loan_id")
    create_loan.add_argument("book_id")

    return_loan = commands.add_parser("return-loan")
    return_loan.add_argument("loan_id")
    return parser


def print_book(book):
    print(
        f"{book['ID']} | {book['title']} | "
        f"available: {book['available_copies']}/{book['total_copies']}"
    )


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)

    try:
        library = Library(args.file)
        if args.command == "add-book":
            print_book(library.add_book(args.book_id, args.title, args.copies))
        elif args.command == "list-books":
            for book in library.list_books():
                print_book(book)
        elif args.command == "show-book":
            print_book(library.show_book(args.book_id))
        elif args.command == "create-loan":
            library.create_loan(args.loan_id, args.book_id)
            print(f"Created loan {args.loan_id}")
        elif args.command == "return-loan":
            library.return_loan(args.loan_id)
            print(f"Returned loan {args.loan_id}")
        return 0
    except ValueError as error:
        print(f"Validation error: {error}", file=sys.stderr)
        return 2
    except LibraryError as error:
        print(f"Storage error: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
