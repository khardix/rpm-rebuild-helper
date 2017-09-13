"""Command Line Interface for the package"""

from contextlib import ExitStack
from itertools import chain

import click
import toml

from . import configuration, util
from .service.abc import Repository


@click.group()
@click.pass_context
def main(context):
    """RPM Rebuild Helper – an automation tool for mass RPM rebuilding,
    with focus on Software Collections.
    """

    # Load service configuration
    all_config_streams = chain(
        util.open_config_files(extension='.service.toml'),
        util.open_resource_files(root_dir='conf.d', extension='.service.toml'),
    )

    with ExitStack() as opened:
        streams = map(opened.enter_context, all_config_streams)
        contents = map(toml.load, streams)

        context.obj = configuration.Context.from_merged(*contents)


@main.command()
@click.option(
    '--from', '-f', 'source_group',
    help='Name of the source tag.',
)
@click.option(
    '--to', '-t', 'dest_group',
    help='Name of the destination tag.',
)
@click.option('--el', type=click.IntRange(6, 8), help='EL version.')
@click.option('--collection', '-c', help='Collection name.')
@click.pass_obj
def diff(config, source_group, dest_group, el, collection):
    """List all packages from source tag missing in destination tag."""

    def latest_builds(group):
        """Fetch latest builds from a group."""

        tag = config.unalias('tag', group, el=el, collection=collection)
        repo = config.service_index['tag_prefixes'].find(tag, type=Repository)

        yield from repo.latest_builds(tag)

    # Packages present in destination
    present_packages = {
        build.name: build
        for build in latest_builds(dest_group)
        if build.name.startswith(collection)
    }

    def obsolete(package):
        return (
            package.name in present_packages
            and present_packages[package.name] >= package
        )

    missing_packages = (
        pkg for pkg in latest_builds(source_group)
        if pkg.name.startswith(collection)
        and not obsolete(pkg)
    )

    for pkg in sorted(missing_packages, key=lambda pkg: pkg.name):
        print(pkg.nvr)
