"""Command Line Interface for the package"""

from contextlib import ExitStack
from functools import reduce, wraps
from itertools import chain, repeat
from operator import itemgetter
from pathlib import Path
from typing import Callable, Iterator

import attr
import click
import toml
from attr.validators import instance_of
from ruamel import yaml

from . import configuration, util
from .service.abc import Repository


@attr.s(slots=True, frozen=True)
class Parameters:
    """Global run parameters (CLI options, etc.)"""

    #: Source group name
    source = attr.ib(validator=instance_of(str))
    #: Destination group name
    destination = attr.ib(validator=instance_of(str))
    #: EL major version
    el = attr.ib(validator=instance_of(int))

    #: Configured and indexed service instances
    service = attr.ib(validator=instance_of(configuration.InstanceRegistry))

    @service.default
    def load_user_and_bundled_services(_self):
        """Loads all available user and bundled service configuration files."""

        streams = chain(
            util.open_resource_files(
                root_dir='conf.d',
                extension='.service.toml',
            ),
            util.open_config_files(
                extension='.service.toml',
            ),
        )

        with ExitStack() as opened:
            streams = map(opened.enter_context, streams)
            contents = map(toml.load, streams)

            return configuration.InstanceRegistry.from_merged(*contents)


# Command decorators
def processor(func: Callable):
    """Process a sequence of (SCL collection, its package iterator) pairs. """

    @wraps(func)
    def wrapper(*args, **kwargs):
        def bound(stream: Iterator):  # bind args, kwargs, wait for the stream
            return func(stream, *args, **kwargs)
        return bound
    return wrapper


def generator(func: Callable):
    """Add package iterators to a sequence of SCL names.

    Any existing package iterators are discarded.
    """

    @wraps(func)
    @processor
    def wrapper(stream, *args, **kwargs):
        # Discard the existing package iterators
        stream = map(itemgetter(0), stream)
        return func(stream, *args, **kwargs)
    return wrapper


# Commands
@click.group(chain=True)
@click.option(
    '--from', '-f', 'source',
    help='Name of a source group (tag, target, ...).'
)
@click.option(
    '--to', '-t', 'destination',
    help='Name of a destination group (tag, target, ...).'
)
@click.option(
    '--el', '-e', type=click.IntRange(6), default=7,
    help='Major EL version.',
)
@click.option(
    '--collection', '-c', 'collection_seq', multiple=True,
    help='Name of the SCL to work with (can be used multiple times).'
)
@click.pass_context
def main(context, collection_seq, **config_options):
    """RPM Rebuild Helper – an automation tool for mass RPM rebuilding,
    with focus on Software Collections.
    """

    # Store configuration
    context.obj = Parameters(**config_options)


@main.resultcallback()
@click.pass_context
def run_chain(context, processor_seq, collection_seq, **_config_options):
    """Run a sequence of collections through a processor sequence.

    Keyword arguments:
        processor_seq: The callables to apply to the collection sequence.
        collection_seq: The sequence of SCL names to be processed.
    """

    # TODO: Start with latest packages from each collection
    collection_seq = zip(collection_seq, repeat(None))

    # Apply the processors
    pipeline = reduce(
        lambda data, proc: proc(data),
        processor_seq,
        collection_seq
    )

    # Output the results in YAML format
    stdout = click.get_text_stream('stdout', encoding='utf-8')
    for collection, packages in pipeline:
        yaml.dump(
            {collection: sorted(map(str, packages))},
            stream=stdout,
            default_flow_style=False,
        )


@main.command()
@generator
@click.pass_obj
def diff(params, collection_stream):
    """List all packages from source tag missing in destination tag."""

    for collection in collection_stream:
        def latest_builds(group):
            """Fetch latest builds from a group."""

            tag = params.service.unalias(
                'tag', group,
                el=params.el,
                collection=collection
            )
            repo = params.service.index['tag_prefixes'].find(
                tag, type=Repository
            )

            yield from repo.latest_builds(tag)

        # Packages present in destination
        present = {
            build.name: build
            for build in latest_builds(params.destination)
            if build.name.startswith(collection)
        }

        def obsolete(package):
            return (
                package.name in present
                and present[package.name] >= package
            )

        missing = (
            pkg for pkg in latest_builds(params.source)
            if pkg.name.startswith(collection)
            and not obsolete(pkg)
        )

        yield collection, missing


@main.command()
@click.option(
    '--output-dir', '-d', metavar='DIR',
    type=click.Path(file_okay=False, writable=True),
    default='.',
    help='Target directory for downloaded packages [default: "."].'
)
@processor
@click.pass_obj
def download(params, collection_stream, output_dir):
    """Download packages into specified directory."""

    output_dir = Path(output_dir).resolve()

    for collection, packages in collection_stream:
        tag = params.service.unalias(
            'tag', params.source, el=params.el, collection=collection,
        )
        repo = params.service.index['tag_prefixes'].find(tag, type=Repository)
        collection_dir = output_dir / collection

        collection_dir.mkdir(exist_ok=True)

        paths = map(repo.download, packages, repeat(collection_dir))

        yield collection, paths
