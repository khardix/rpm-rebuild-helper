"""Command Line Interface for the package"""

import logging
from collections import defaultdict, OrderedDict
from datetime import timedelta, datetime, timezone
from functools import reduce
from itertools import product
from operator import attrgetter
from pathlib import Path

import attr
import click
from ruamel import yaml

from .tooling import Parameters, Package, PackageStream
from .tooling import stream_processor, stream_generator
from .. import RESOURCE_ID, util, rpm
from ..service.abc import BuildFailure


# Logging setup
logger = logging.getLogger(RESOURCE_ID)
util.logging.basic_config(logger)


# Commands
@click.group(chain=True)
@util.logging.quiet_option(logger)
@click.option(
    '--input', '-i', 'input_file', type=click.File(),
    help='YAML file with input data (or - for standard input).'
)
@click.option(
    '--from', '-f', 'source',
    help='Name of a source group (tag, target, ...).'
)
@click.option(
    '--to', '-t', 'destination',
    help='Name of a destination group (tag, target, ...).'
)
@click.option(
    '--el', '-e', 'el_seq',
    type=click.IntRange(6), multiple=True, default=[7],
    help='Major EL version (can be used multiple times).',
)
@click.option(
    '--collection', '-c', 'collection_seq', multiple=True,
    help='Name of the SCL to work with (can be used multiple times).'
)
@click.option(
    '--all-collections', '--all', 'all_collections',
    is_flag=True, default=False,
    help='Process all non-EOL collections for each EL version.'
)
@click.option(
    '--report', type=click.File(mode='w', encoding='utf-8'),
    default='-',
    help='File name of the final report [default: stdout].',
)
@click.pass_context
def main(context, source, destination, **_options):
    """RPM Rebuild Helper – an automation tool for mass RPM rebuilding,
    with focus on Software Collections.
    """

    # Store configuration
    context.obj = Parameters(cli_options={
        'source': source,
        'destination': destination,
    })


@main.resultcallback()
@click.pass_context
def run_chain(
    context,
    processor_seq,
    input_file,
    collection_seq,
    all_collections,
    el_seq,
    report,
    **_config_options,
):
    """Run a sequence of collections through a processor sequence.

    Keyword arguments:
        processor_seq: The callables to apply to the collection sequence.
        collection_seq: The sequence of SCL names to be processed.
        all_collections: Override collection_seq by all non-EOL collections
            for each EL version.
        el_seq: The sequence of EL versions to be processed.
        report: The file to write the result report into.
    """

    main_config = context.obj.main_config

    # Create placeholders for all collections and EL versions
    if all_collections:
        session = util.net.default_requests_session()
        packages = []
        for el in el_seq:
            url = main_config['remote']['collection-list'].format(el=el)
            content = util.net.fetch(url, encoding='ascii', session=session)
            lines = filter(lambda l: 'EOL' not in l, content.splitlines())
            collections = (l.strip() for l in lines)
            packages += (Package(el, scl) for scl in collections)
        package_stream = PackageStream(packages)

    # Load packages from YAML
    elif input_file:
        package_stream = PackageStream.from_yaml(input_file)

    else:
        package_stream = PackageStream(
            [Package(*pair) for pair in product(el_seq, collection_seq)]
        )

    # Apply the processors
    pipeline = reduce(
        lambda data, proc: proc(data),
        processor_seq,
        package_stream,
    )

    # Output the results in YAML format
    PackageStream.consume(pipeline).to_yaml(stream=report)


@main.command()
@click.option(
    '--min-days', type=click.INT, default=0,
    help='Minimum age of the build in destination to qualify for the check.',
)
@click.option(
    '--simple-dist/--no-simple-dist', default=True,
    help='Use simple dist tag for comparison (i.e. el7 instead of el7_4).',
)
@stream_generator(source='tag', destination='tag')
def diff(collection_stream, min_days, simple_dist):
    """List all packages from source tag missing in destination tag."""

    log = logger.getChild('diff')

    for scl in collection_stream:
        destination_builds = scl.destination.service.latest_builds(
            scl.destination.label,
        )
        source_builds = scl.source.service.latest_builds(
            scl.source.label,
        )

        log.info('Comparing {p.collection}-el{p.el}'.format(p=scl))

        # Packages present in destination
        present = {
            build.name: rpm.shorten_dist_tag(build) if simple_dist else build
            for build in destination_builds
            if build.name.startswith(scl.collection)
        }

        def obsolete(package):
            return (
                package.name in present
                and present[package.name] >= package
            )

        missing = {
            pkg for pkg in source_builds
            if pkg.name.startswith(scl.collection)
            and not obsolete(rpm.shorten_dist_tag(pkg) if simple_dist else pkg)
        }

        def old_enough(package):
            try:
                entry_time = scl.source.service.tag_entry_time(
                    tag_name=scl.source.label,
                    build=package,
                )
            except NotImplementedError as err:
                message = '[{pkg}] {err!s}, skipping.'.format(
                    pkg=package,
                    err=err,
                )
                log.warning(message)

                return False

            if entry_time is None:
                message = '[{pkg}] Not present in {source}, skipping.'.format(
                    pkg=package,
                    source=scl.source.label,
                )
                log.warning(message)

                return False

            age = datetime.now(tz=timezone.utc) - entry_time
            return age >= timedelta(days=min_days)

        if min_days:
            ready = filter(old_enough, missing)
        else:
            ready = missing

        yield from (attr.evolve(scl, metadata=package) for package in ready)


@main.command()
@click.option(
    '--output-dir', '-d', metavar='DIR',
    type=click.Path(file_okay=False, writable=True),
    default='.',
    help='Target directory for downloaded packages [default: "."].'
)
@stream_processor(source='tag')
def download(package_stream, output_dir):
    """Download packages into specified directory."""

    log = logger.getChild('download')
    output_dir = Path(output_dir).resolve()

    for pkg in package_stream:
        collection_dir = output_dir / pkg.collection
        collection_dir.mkdir(exist_ok=True)

        log.info('Fetching {}'.format(pkg.metadata))
        local = pkg.source.service.download(pkg.metadata, collection_dir)

        yield attr.evolve(pkg, metadata=local)


@main.command()
@click.option(
    '--failed', '-f', 'fail_file',
    type=click.File(mode='w', encoding='utf-8', lazy=True),
    help='Path to store build failures to [default: stderr].',
)
@stream_processor(destination='target')
def build(package_stream, fail_file):
    """Attempt to build packages in target."""

    failed = defaultdict(set)

    for pkg in package_stream:
        with pkg.destination.service as builder:
            try:
                built = builder.build(pkg.destination.label, pkg.metadata)
                yield attr.evolve(pkg, metadata=built)
            except BuildFailure as failure:
                failed[pkg.collection].add(failure)

    if not failed:
        raise StopIteration()

    # Convert the stored exceptions to readable representation
    readable_failures = {
        scl: OrderedDict(
            (f.package.nevra, f.reason)
            for f in sorted(fails, key=attrgetter('package'))
        ) for scl, fails in failed.items()
    }

    if fail_file is None:
        fail_file = click.get_text_stream('stderr', encoding='utf-8')

    yaml.dump(
        readable_failures,
        stream=fail_file,
        default_flow_style=False,
    )


@main.command()
@click.option(
    '--owner',
    default=None,
    help='Name of the owner for new packages in tag.',
)
@stream_processor(destination='tag')
def tag(package_stream, owner):
    """Tag builds to target."""

    for pkg in package_stream:
        with pkg.destination.service as repo:
            tagged = repo.tag_build(pkg.destination.label, pkg.metadata)
            yield attr.evolve(pkg, metadata=tagged)
