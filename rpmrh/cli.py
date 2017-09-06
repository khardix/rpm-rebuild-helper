"""Command Line Interface for the package"""

from contextlib import ExitStack
from itertools import chain, filterfalse

import click
import toml

from . import configuration, util


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
@click.pass_obj
def diff(config, source_group, dest_group):
    """List all packages from source tag missing in destination tag."""

    source_service = config.index['tag'][source_group]
    dest_service = config.index['tag'][dest_group]

    # Packages present in destination
    present_packages = {
        build.name: build
        for build in dest_service.latest_builds(dest_group)
    }

    def obsolete(package):
        return (
            package.name in present_packages
            and present_packages[package.name] >= package
        )

    missing_candidates = source_service.latest_builds(source_group)
    missing_packages = filterfalse(obsolete, missing_candidates)

    for pkg in sorted(missing_packages, key=lambda pkg: pkg.name):
        print(pkg.nvr)
