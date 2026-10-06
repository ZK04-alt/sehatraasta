from dataclasses import dataclass

from .enums import ProvenanceType


@dataclass
class Provenance:
    source_type: ProvenanceType
    source: str | None = None
    source_identifier: str | None = None

    def checks(self):
        if not isinstance(self.source_type, ProvenanceType):
            raise ValueError("unknown provenance type")

        # Unknown source type does not discard any reference the user does know.
        if self.source is not None and not isinstance(self.source, str):
            raise ValueError("invalid source")
        if isinstance(self.source, str) and not self.source.strip():
            self.source = None
        if self.source_identifier is not None and not isinstance(self.source_identifier, str):
            raise ValueError("invalid source identifier")
        if isinstance(self.source_identifier, str) and not self.source_identifier.strip():
            self.source_identifier = None

    def __post_init__(self):
        self.checks()
