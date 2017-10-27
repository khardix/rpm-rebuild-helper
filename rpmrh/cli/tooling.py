"""Additional CLI-specific tooling"""

from collections import defaultdict
from copy import deepcopy
from functools import partial, wraps
from itertools import groupby, starmap
from operator import attrgetter, itemgetter
from typing import Iterator, Optional, Union
from typing import Mapping, TextIO, Callable

import attr
import click
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
    #: If None, package acts as a placeholder for an empty collection
    metadata = attr.ib(
        default=None,
        validator=optional(instance_of(rpm.Metadata)),
    )

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


def stream_processor(
    command: Optional[Callable] = None,
    **option_kind,
) -> Callable:
    """Command decorator for processing a package stream.

    This decorator adjust the Package iterator
    and then injects it to the wrapped command
    as first positional argument.

    Keyword arguments:
        CLI option name to a group kind.
        Each matching CLI option will be interpreted
        as a group name or alias
        and resolved as such for all packages
        passing through to the wrapped command.

    Returns:
        The wrapped command.
    """

    if command is None:
        return partial(stream_processor, **option_kind)

    @wraps(command)
    @click.pass_context
    def wrapper(context, *command_args, **command_kwargs):
        """Construct a closure that adjusts the stream and wraps the command.
        """

        # Need Parameters for the CLI options and service registry
        parameters = context.find_object(Parameters)

        # Prepare the group(s) expansion
        def expand_groups(package: Package) -> Package:
            """Expand all specified groups for the passed package."""

            group_map = {
                option: PackageGroup(*parameters.service_registry.resolve(
                    name_or_alias=parameters.cli_options[option],
                    kind=kind,
                    alias_format_map=attr.asdict(package, recurse=False),
                ))
                for option, kind in option_kind.items()
            }

            return attr.evolve(package, **group_map)

        @wraps(command)
        def processor(stream: Iterator[Package]) -> Iterator[Package]:
            """Expand the groups and inject the stream to the command."""

            stream = map(expand_groups, stream)
            return context.invoke(
                command, stream, *command_args, **command_kwargs,
            )
        return processor
    return wrapper


# TODO: POC, re-examine/review again
def stream_generator(command: Callable = None, **option_kind):
    """Command decorator for generating a package stream.

    Packages in the stream are grouped by (el, collection)
    and the actual metadata are discarded.
    It is assumed that the decorated command will generate
    new metadata for each group.

    Keyword arguments:
        Same as for stream_processor().

    Returns:
        The wrapped command.
    """

    if command is None:
        return partial(stream_generator, **option_kind)

    @wraps(command)
    def wrapper(*args, **kwargs):
        # Obtain the processor
        processor = stream_processor(command, **option_kind)(*args, **kwargs)

        @wraps(command)
        def generator(stream: Iterator[Package]) -> Iterator[Package]:
            # Group the packages, discard metadata
            groupings = groupby(stream, attrgetter('el', 'collection'))
            keys = map(itemgetter(0), groupings)
            placeholders = starmap(Package, keys)

            return processor(placeholders)
        return generator
    return wrapper
