"""Additional CLI-specific tooling"""

from collections import defaultdict
from copy import deepcopy
from typing import Iterator, Optional

import attr
from ruamel import yaml
from attr.validators import optional, instance_of

from .. import rpm


# Add YAML dump capabilities for python types not supported by default
YAMLDumper = deepcopy(yaml.SafeDumper)
YAMLDumper.add_representer(defaultdict, lambda r, d: r.represent_dict(d))


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
