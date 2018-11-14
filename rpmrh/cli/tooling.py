"""Additional CLI-specific tooling"""

import logging
from collections import defaultdict
from copy import deepcopy
from functools import partial, wraps
from itertools import groupby
from operator import attrgetter, itemgetter
from typing import Iterator, Optional, Union
from typing import Mapping, TextIO, Callable

import attr
import click
from ruamel import yaml
from attr.validators import optional, instance_of

from .. import rpm


LOG = logging.getLogger(__name__)

# Add YAML dump capabilities for python types not supported by default
YAMLDumper = deepcopy(yaml.SafeDumper)
YAMLDumper.add_representer(defaultdict, lambda r, d: r.represent_dict(d))


#
# Data classes
#


@attr.s(slots=True, frozen=True)
class SCL:
    """Software collection description"""

    #: Collection name
    collection = attr.ib(validator=instance_of(str))
    #: EL version of the collection
    el = attr.ib(validator=instance_of(int))


@attr.s(slots=True, frozen=True)
class Package:
    """Metadata and context of processed package"""

    #: Data of the associated collection
    scl = attr.ib(validator=instance_of(SCL))

    #: RPM metadata of the package
    metadata = attr.ib(validator=optional(instance_of(rpm.Metadata)), default=None)

    # TODO: Get rid of the following attributes;
    # they are properties of COMMAND, not package

    #: The source group for this package
    source = attr.ib(default=None, validator=optional(instance_of(Mapping)), cmp=False)
    #: The destination group for this package
    destination = attr.ib(
        default=None, validator=optional(instance_of(Mapping)), cmp=False
    )


@attr.s(slots=True, frozen=True)
class PackageStream:
    """Encapsulation of stream of processed packages."""

    #: Internal storage for the packages
    _container = attr.ib(
        default=frozenset(), validator=instance_of(frozenset), converter=frozenset
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
            structure[pkg.scl.el][pkg.scl.collection].append(str(pkg.metadata))

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
                metadata=rpm.Metadata.from_nevra(nevra),
                scl=SCL(collection=collection, el=el),
            )
            for el, collection_map in structure.items()
            for collection, pkg_list in collection_map.items()
            for nevra in pkg_list
        )


def stream_processor(command: Optional[Callable] = None, **option_kind) -> Callable:
    """Command decorator for processing a package stream.

    This decorator adjust the Package iterator
    and then injects it to the wrapped command
    as first positional argument.

    Keyword arguments:
        source: The kind of source service (repo, build, test).
        destination: The kind of destination service (repo, build, test).

    Returns:
        A wrapper around the command.
        Note that the command is changed to return a prepared action.
    """

    if command is None:
        return partial(stream_processor, **option_kind)

    @wraps(command)
    @click.pass_context
    def wrapper(context, *command_args, **command_kwargs):
        """Command wrapper in charge of service selection.

        The responsibility is twofold:
        1. Ensure that proper service kind exists and attach it to the package.
        2. Expand all format strings with information about current SCL.

        Arguments:
            context: Current context, injected by Click.

        Returns:
            The command with bound arguments, waiting for the stream to
            process.
        """

        log = LOG.getChild("stream_processor")

        configuration = context.obj
        log.debug(
            "{cmd.__name__} configuration: {conf}".format(
                cmd=command, conf=configuration
            )
        )

        def locate_service(package: Package) -> Package:
            """Attach appropriate services to the package."""

            # 'source': configuration['source']['repo']
            services = {
                key: configuration[key][kind].copy()
                for key, kind in option_kind.items()
            }

            return attr.evolve(package, **services)

        def format_labels(package: Package) -> Package:
            """Process all format strings."""

            for group in filter(None, (package.source, package.destination)):
                for key in group.keys() & {"tags", "targets", "tests"}:
                    group[key] = [
                        l.format_map(attr.asdict(package.scl)) for l in group[key]
                    ]

            return package

        # This changes
        @wraps(command)
        def processor(stream: Iterator[Package]) -> Iterator[Package]:
            """The prepared command.

            This is a wrapper over the actual command which postpones
            its execution until the stream of packages is available.
            For details, see `Click documentation`_
            and associated `example`_.

            .. _Click documentation: http://click.pocoo.org/6/commands/#multi-command-pipelines  # noqa: E501
            .. _example: https://github.com/mitsuhiko/click/tree/master/examples/imagepipe  # noqa: E501
            """

            # Transform the stream using the prepared operations
            stream = map(locate_service, stream)
            stream = map(format_labels, stream)

            return context.invoke(command, stream, *command_args, **command_kwargs)

        return processor  # wrapper returns processor

    return wrapper  # stream_processor returns wrapper


# TODO: POC, re-examine/review again
def stream_generator(command: Callable = None, **option_kind):
    """Command decorator for generating a package stream.

    Packages in the stream are grouped by scl,
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
            groupings = groupby(stream, attrgetter("scl"))
            keys = map(itemgetter(0), groupings)
            placeholders = (Package(scl=scl) for scl in keys)

            return processor(placeholders)

        return generator

    return wrapper
