from dataclasses import dataclass
from enum import Enum
import sys


class Status(Enum):
    CREATED = "created"
    IN_TRANSIT = "in transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@dataclass
class Parcel:
    id: str
    destination: str
    weight: float
    status: Status

    def change_status(self, n_status):
        if self.status == Status.CREATED and (
            n_status == Status.IN_TRANSIT or n_status == Status.CANCELLED
        ):
            self.status = n_status
        elif self.status == Status.IN_TRANSIT and n_status == Status.DELIVERED:
            self.status = n_status
        else:
            raise ValueError("incorrect transition")

    def __post_init__(self):
        self.checks()

    def checks(self):
        if not self.id:
            raise ValueError("missing id")

        elif not self.destination:
            raise ValueError("missing destination")

        elif self.weight == "":
            raise ValueError("missing weight")

        elif not isinstance(self.weight, (int, float)):
            raise ValueError("invalid weight")

        elif self.weight <= 0:
            raise ValueError("non positive weight")

        elif not isinstance(self.status, Status):
            raise ValueError("unknown status")

        def __str__(self):
            return f"id is {self.id} \ndestination is {self.destination}\nweight is {self.weight}\nstatus is {self.status.value}"


def main():
    try:
        id = input("ID: ")
        destination = input("destination: ")
        weight = float(input("weight: "))
        status = Status.CREATED
        parcel = Parcel(id, destination, weight, status)
        print(f"\nRecord is created\n")
        print(parcel)
        transition_choice = int(input("\nchange status?\n1. yes\n2. no\n"))
        if transition_choice == 1:
            new_status = int(
                input("enter new state:\n1. IN_TRANSIT\n2. DELIVERED\n3. CANCELLED\n")
            )
            if new_status == 1:
                n_status = Status.IN_TRANSIT
                parcel.change_status(n_status)
            elif new_status == 2:
                n_status = Status.DELIVERED
                parcel.change_status(n_status)
            elif new_status == 3:
                n_status = Status.CANCELLED
                parcel.change_status(n_status)
            else:
                sys.exit("invalid number")
            print(parcel)

        else:
            sys.exit()
    except ValueError as e:
        print(f"Validation Error: {e}")


if __name__ == "__main__":
    main()
