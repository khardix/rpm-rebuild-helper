"""Additional CLI-specific tooling"""


import attr
from attr.validators import optional, instance_of

from .. import rpm


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
