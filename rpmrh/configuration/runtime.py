"""Run-time CLI and miscellaneous configuration"""

from functools import partial
from typing import Any, Mapping

import attr

from . import _validation, service, phase
from ._validation import InvalidConfiguration  # noqa: F401
from ._loading import load_matching_configuration
from .service import make_instance_map

#: Description of the miscellaneous run-time options
SCHEMA = {"collection_list_url": {"type": "string", "required": True}}

# Configuration file processing
validate = partial(_validation.validate, schema=SCHEMA)


@attr.s(slots=True, frozen=True)
class Settings:
    """Aggregate of run-time settings"""

    #: URL template for remote collection name listing
    collection_list_url: str = attr.ib()
    #: Known services
    service: Mapping[str, Any] = attr.ib(converter=make_instance_map)
    #: Known phases
    phase: Mapping[str, Any] = attr.ib()

    @phase.validator
    def __validate_phase_map(
        self, _attribute: Any, phase_map: Mapping[str, Mapping]
    ) -> None:
        phase_map = phase.validate_integrity(phase_map, self.service)

    @classmethod
    def from_configuration(
        cls,
        runtime_glob: str = "config.toml",
        service_glob: str = "*.service.toml",
        phase_glob: str = "*.phase.toml",
    ) -> "Settings":
        """Load the settings from configuration files.

        Keyword arguments:
            runtime_glob: File name glob for run time configuration files.
            service_glob: File name glob for service configuration files.
            phase_glob: File name glob for phase configuration files.

        Returns:
            New instance of run time settings.
        """

        return cls(
            **validate(load_matching_configuration(runtime_glob)),
            service=service.validate(load_matching_configuration(service_glob)),
            phase=phase.validate(load_matching_configuration(phase_glob)),
        )
