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

        if self.source_type == ProvenanceType.NOT_SUPPLIED:
            if self.source is not None or self.source_identifier is not None:
                raise ValueError("source details conflict with not supplied")
            return

        if self.source is None:
            raise ValueError("missing source")
        if not isinstance(self.source, str):
            raise ValueError("invalid source")
        if not self.source.strip():
            raise ValueError("missing source")

        if self.source_identifier is None:
            raise ValueError("missing source identifier")
        if not isinstance(self.source_identifier, str):
            raise ValueError("invalid source identifier")
        if not self.source_identifier.strip():
            raise ValueError("missing source identifier")

    def __post_init__(self):
        self.checks()
