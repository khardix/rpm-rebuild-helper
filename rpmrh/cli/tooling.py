"""Additional CLI-specific tooling"""

from collections import defaultdict
from copy import deepcopy
from typing import Iterator, Optional, Union
from typing import Mapping, TextIO

import attr
from ruamel import yaml
from attr.validators import optional, instance_of

from .. import rpm
from ..configuration import service
from ..configuration.runtime import load_configuration, load_services


# Add YAML dump capabilities for python types not supported by default
YAMLDumper = deepcopy(yaml.SafeDumper)
YAMLDumper.add_representer(defaultdict, lambda r, d: r.represent_dict(d))


@attr.s(slots=True, frozen=True)
class Parameters:
    """A structure holding parameters for single application run."""

    #: Parsed command-line parameters
    cli_options = attr.ib(validator=instance_of(Mapping))

    #: Main configuration values
    main_config = attr.ib(
        default=attr.Factory(load_configuration),
        validator=instance_of(Mapping),
    )

    #: Known service registry
    service_registry = attr.ib(
        default=attr.Factory(load_services),
        validator=instance_of(service.Registry),
    )


@attr.s(slots=True, frozen=True, cmp=False)
class PackageGroup:
    """A label and associated service for a group of related packages."""

    #: Group label (tag, target, etc.)
    label = attr.ib(validator=instance_of(str))
    #: Associated service interface
    service = attr.ib()


@attr.s(slots=True, frozen=True)
class Package:
    """Metadata and context of processed package"""

    #: EL version of the package
    el = attr.ib(validator=instance_of(int))
    #: The collection to which the package belongs
    collection = attr.ib(validator=instance_of(str))
    #: RPM metadata of the package
    metadata = attr.ib(validator=instance_of(rpm.Metadata))

    #: The source group for this package
    source = attr.ib(
        default=None,
        validator=optional(instance_of(PackageGroup)),
        cmp=False,
    )
    #: The destination group for this package
    destination = attr.ib(
        default=None,
        validator=optional(instance_of(PackageGroup)),
        cmp=False,
    )


@attr.s(slots=True, frozen=True)
class PackageStream:
    """Encapsulation of stream of processed packages."""

    #: Internal storage for the packages
    _container = attr.ib(
        default=frozenset(),
        validator=instance_of(frozenset),
        convert=frozenset,
    )

    def __iter__(self):
        """Iterate over the packages in deterministic manner."""

        yield from sorted(self._container)

    @classmethod
    def consume(cls, iterator: Iterator[Package]):
        """Create a new Stream by consuming a Package iterator."""

        return cls(iterator)

    def to_yaml(self, stream: Optional[TextIO] = None):
        """Serialize packages in the stream to YAML format.

        Keyword arguments:
            stream: The file stream to write the result into.
        """

        structure = defaultdict(lambda: defaultdict(list))

        for pkg in sorted(self._container):
            structure[pkg.el][pkg.collection].append(str(pkg.metadata))

        return yaml.dump(structure, stream, Dumper=YAMLDumper)

    @classmethod
    def from_yaml(cls, structure_or_stream: Union[Mapping, TextIO]):
        """Create a new Stream from YAML format.

        Keyword arguments:
            structure_or_stream: The object to read the packages from.
                Either a mapping
                (interpreted as an already converted YAML structure)
                or an opened file stream to read the data from,
                or an YAML-formatted string.

        Returns:
            New PackageStream constructed from the input data.
        """

        if isinstance(structure_or_stream, Mapping):
            structure = structure_or_stream

        elif isinstance(structure_or_stream, (TextIO, str)):
            structure = yaml.safe_load(structure_or_stream)

        else:
            message = 'Unsupported value type: {}'.format(
                type(structure_or_stream)
            )
            raise ValueError(message)

        return cls(
            Package(
                el=el,
                collection=scl,
                metadata=rpm.Metadata.from_nevra(nevra),
            )
            for el, collection_map in structure.items()
            for scl, pkg_list in collection_map.items()
            for nevra in pkg_list
        )
