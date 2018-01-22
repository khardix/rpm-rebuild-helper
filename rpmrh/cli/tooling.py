"""Additional CLI-specific tooling"""

from collections import defaultdict
from contextlib import ExitStack
from copy import deepcopy
from functools import partial, wraps
from itertools import groupby, starmap, chain
from operator import attrgetter, itemgetter
from typing import Iterator, Optional, Union
from typing import Mapping, TextIO, Callable

import attr
import click
import toml
from ruamel import yaml
from attr.validators import optional, instance_of

from .. import rpm
from ..util.filesystem import open_resource_files, open_config_files


# Add YAML dump capabilities for python types not supported by default
YAMLDumper = deepcopy(yaml.SafeDumper)
YAMLDumper.add_representer(defaultdict, lambda r, d: r.represent_dict(d))


def load_configuration(
    glob: str,
    *,
    interpret: Callable[[TextIO], Mapping] = toml.load,
    validate: Callable[[Mapping], Mapping] = lambda m: m,
) -> Iterator[Mapping]:
    """Load configuration contents from both bundled and system files.

    Keyword arguments:
        glob: File name (NOT path) glob matching the requested files.
        interpret: Converter from text stream to Python objects.
            Defaults to toml.load().
        validate: Validation and normalization of single configuration file.
            Should raise an exception on validation failure.
            Defaults to pass-through lambda -- no validation or normalization.

    Yields:
        Interpreted contents of configuration files.
        The order is from most (user) specific to most generic (bundled) ones.
    """

    with ExitStack() as opened:
        system = map(opened.enter_context, open_config_files(glob))
        bundle = map(opened.enter_context, open_resource_files('conf.d', glob))
        streams = chain(system, bundle)

        interpreted = map(interpret, streams)
        validated = map(validate, interpreted)

        yield from validated


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
        validator=optional(instance_of(Mapping)),
        cmp=False,
    )
    #: The destination group for this package
    destination = attr.ib(
        default=None,
        validator=optional(instance_of(Mapping)),
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
        else:
            structure = yaml.safe_load(structure_or_stream)

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

        parameters = context.ensure_object(dict)

        # Prepare the group(s) expansion
        def expand_groups(package: Package) -> Package:
            """Expand all specified groups for the passed package."""

            group_map = {
                option: parameters[option][kind]
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
