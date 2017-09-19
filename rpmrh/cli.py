"""Command Line Interface for the package"""

from contextlib import ExitStack
from itertools import chain

import attr
import click
import toml
from attr.validators import instance_of

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
pass_parameters = click.make_pass_decorator(Parameters)


@click.group()
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
@click.pass_context
def main(context, **config_options):
    """RPM Rebuild Helper – an automation tool for mass RPM rebuilding,
    with focus on Software Collections.
    """

    # Store configuration
    context.obj = Parameters(**config_options)


@main.command()
@click.option('--collection', '-c', help='Collection name.')
@pass_parameters
def diff(params, collection):
    """List all packages from source tag missing in destination tag."""

    def latest_builds(group):
        """Fetch latest builds from a group."""

        tag = params.service.unalias(
            'tag', group,
            el=params.el,
            collection=collection
        )
        repo = params.service.index['tag_prefixes'].find(tag, type=Repository)

        yield from repo.latest_builds(tag)

    # Packages present in destination
    present_packages = {
        build.name: build
        for build in latest_builds(params.destination)
        if build.name.startswith(collection)
    }

    def obsolete(package):
        return (
            package.name in present_packages
            and present_packages[package.name] >= package
        )

    missing_packages = (
        pkg for pkg in latest_builds(params.source)
        if pkg.name.startswith(collection)
        and not obsolete(pkg)
    )

    for pkg in sorted(missing_packages, key=lambda pkg: pkg.name):
        print(pkg.nvr)
