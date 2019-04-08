"""Command Line Interface for the package"""
import logging
from collections import defaultdict
from collections import OrderedDict
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import lru_cache
from functools import reduce
from itertools import chain
from itertools import product
from operator import attrgetter
from pathlib import Path
from typing import Iterator

import attr
import click
from ruamel import yaml

from .. import configuration
from .. import RESOURCE_ID
from .. import rpm
from .. import util
from ..configuration._loading import load_matching_configuration
from ..exception import UserError
from ..service.abc import BuildFailure
from ..service.jenkins import UnknownJob
from .tooling import Package
from .tooling import PackageStream
from .tooling import SCL
from .tooling import stream_generator
from .tooling import stream_processor


# Logging setup
logger = logging.getLogger(RESOURCE_ID)
util.logging.basic_config(logger)


# TODO Unify with other configuration errors
class ConfigurationMismatch(UserError):
    lead = "Configuration mismatch"


# Commands
@click.group(chain=True, invoke_without_command=True)
@util.logging.quiet_option(logger)
@click.version_option()
@click.option(
    "--input",
    "-i",
    "input_file",
    type=click.File(),
    help="YAML file with input data (or - for standard input).",
)
@click.option(
    "--from", "-f", "source", help="Name of a source group (tag, target, ...)."
)
@click.option(
    "--to", "-t", "destination", help="Name of a destination group (tag, target, ...)."
)
@click.option(
    "--el",
    "-e",
    "el_seq",
    type=click.IntRange(6, None),
    multiple=True,
    default=[6, 7],
    help="Major EL version (can be used multiple times).",
)
@click.option(
    "--collection",
    "-c",
    "collection_seq",
    multiple=True,
    help="Name of the SCL to work with (can be used multiple times).",
)
@click.option(
    "--all-collections",
    "--all",
    "all_collections",
    is_flag=True,
    default=False,
    help="Process all non-EOL collections for each EL version.",
)
@click.option(
    "--report",
    type=click.File(mode="w", encoding="utf-8"),
    default="-",
    help="File name of the final report [default: stdout].",
)
@click.pass_context
def main(context, source, destination, **_options):
    """RPM Rebuild Helper – an automation tool for mass RPM rebuilding,
    with focus on Software Collections.
    """

    log = logger.getChild("main_setup")

    # Load configured phases
    phase = configuration.phase.validate(load_matching_configuration("*.phase.toml"))

    # Load service configuration
    service_conf = configuration.service.validate(
        load_matching_configuration("*.service.toml")
    )
    service = {
        name: configuration.service.make_instance(conf)
        for name, conf in service_conf.items()
    }

    # Fill configuration dictionary
    context.obj = load_matching_configuration("config.toml")
    log.debug("configuration:", dict(context.obj))

    def extract_services(phase_name: str) -> dict:
        try:
            skeleton = phase[phase_name]
        except KeyError as err:
            message = "Unknown phase: {!s}".format(err)
            raise ConfigurationMismatch(message) from None

        try:
            for kind in skeleton.values():
                kind["service"] = service[kind["service"]]
        except KeyError as err:
            message = "Unknown service: {!s}".format(err)
            raise ConfigurationMismatch(message) from None

        return skeleton

    if source is not None:
        context.obj["source"] = extract_services(source)
        log.debug("source:", source)
    if destination is not None:
        context.obj["destination"] = extract_services(destination)
        log.debug("destination:", destination)


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

    main_config = context.obj

    def fetch_collection_list(el: int) -> Iterator[SCL]:
        """Retrieve collection list from configured remote"""

        url = main_config["remote"]["collection-list"].format(el=el)
        content = util.net.fetch(url, encoding="ascii")

        # Filter EOL collections
        lines = filter(lambda line: "EOL" not in line, content.splitlines())
        collections = (line.strip() for line in lines)
        yield from (SCL(el=el, collection=c) for c in collections)

    # Create placeholders for all collections and EL versions
    if all_collections:
        collections = chain.from_iterable(map(fetch_collection_list, el_seq))
        package_stream = PackageStream(Package(scl=c) for c in collections)

    # Load packages from YAML
    elif input_file:
        package_stream = PackageStream.from_yaml(input_file)

    else:
        collections = (
            SCL(el=el, collection=collection)
            for el, collection in product(el_seq, collection_seq)
        )
        package_stream = PackageStream(Package(scl=scl) for scl in collections)

    # Apply the processors
    pipeline = reduce(lambda data, proc: proc(data), processor_seq, package_stream)

    # Output the results in YAML format
    PackageStream.consume(pipeline).to_yaml(stream=report)


@main.command()
@click.option(
    "--min-days",
    type=click.INT,
    default=None,
    help="Minimum age of the build in destination to qualify for the check.",
)
@click.option(
    "--simple-dist/--no-simple-dist",
    default=True,
    help="Use simple dist tag for comparison (i.e. el7 instead of el7_4).",
)
@stream_generator(source="repo", destination="repo")
def diff(package_stream, min_days, simple_dist):
    """List all packages from source tag missing in destination tag."""

    log = logger.getChild("diff")

    # Filter implementations
    def latest_builds(group):
        builds = chain.from_iterable(
            group["service"].latest_builds(tag) for tag in group["tags"]
        )

        if simple_dist:
            return {rpm.shorten_dist_tag(b) for b in builds}
        else:
            return builds

    def obsolete(package, target_map):
        return package.name in target_map and target_map[package.name] >= package

    def old_enough(package, source_map):
        # Skip this check if not explicitly requested
        if min_days is None:
            return True

        # Attempt to extract tag entry times
        try:
            entry_times = [
                source_map["service"].tag_entry_time(tag_name=tag, build=package)
                for tag in source_map["tags"]
            ]
        except NotImplementedError as err:
            message = "[{pkg}] {err!s}, skipping.".format(pkg=package, err=err)
            log.warning(message)

            return False

        # Compare min_days with latest entry time
        now = datetime.now(tz=timezone.utc)
        entry_time = max(filter(None, entry_times), default=now)
        return (now - entry_time) >= timedelta(days=min_days)

    def has_collection_prefix(build, collection):
        """The package name indicates that it is the part of the collection"""

        return build.name == collection or build.name.startswith(collection + "-")

    # SCL processing
    for pkg in package_stream:
        try:
            destination_builds = latest_builds(pkg.destination)
            source_builds = latest_builds(pkg.source)

            log.info("Comparing {s.collection}-el{s.el}".format(s=pkg.scl))

            # Packages present in destination
            present = {
                build.name: build
                for build in destination_builds
                if has_collection_prefix(build, pkg.scl.collection)
            }

            missing = {
                build
                for build in source_builds
                if has_collection_prefix(build, pkg.scl.collection)
                and not obsolete(build, present)
            }

            ready = filter(lambda build: old_enough(build, pkg.source), missing)

            yield from (attr.evolve(pkg, metadata=package) for package in ready)

        except Exception as err:
            log.error(err)


@main.command()
@click.option(
    "--output-dir",
    "-d",
    metavar="DIR",
    type=click.Path(file_okay=False, writable=True),
    default=".",
    help='Target directory for downloaded packages [default: "."].',
)
@stream_processor(source="repo")
def download(package_stream, output_dir):
    """Download packages into specified directory."""

    log = logger.getChild("download")
    output_dir = Path(output_dir).resolve()

    for pkg in package_stream:
        collection_dir = output_dir / pkg.scl.collection
        collection_dir.mkdir(exist_ok=True)

        log.info("Fetching {}".format(pkg.metadata))
        local = pkg.source["service"].download(pkg.metadata, collection_dir)

        yield attr.evolve(pkg, metadata=local)


@main.command()
@click.option(
    "--failed",
    "-f",
    "fail_file",
    type=click.File(mode="w", encoding="utf-8", lazy=True),
    help="Path to store build failures to [default: stderr].",
)
@stream_processor(destination="build")
def build(package_stream, fail_file):
    """Attempt to build packages in target."""

    failed = defaultdict(lambda: defaultdict(set))

    for pkg in package_stream:
        with pkg.destination["service"] as builder:
            # TODO potentially duplicates packages (one per target!)
            for target in pkg.destination["targets"]:
                try:
                    built = builder.build(target, pkg.metadata)
                    yield attr.evolve(pkg, metadata=built)
                except BuildFailure as failure:
                    failed[pkg.scl.collection][target].add(failure)

    if not failed:
        return

    # Convert the stored exceptions to readable representation
    readable_failures = {
        scl: {
            target: OrderedDict(
                (f.package.nevra, f.reason)
                for f in sorted(fails, key=attrgetter("package"))
            )
            for target, fails in targets.items()
        }
        for scl, targets in failed.items()
    }

    if fail_file is None:
        fail_file = click.get_text_stream("stderr", encoding="utf-8")

    yaml.dump(readable_failures, stream=fail_file, default_flow_style=False)


@main.command()
@click.option(
    "--owner", default=None, help="Name of the owner for new packages in tag."
)
@stream_processor(destination="repo")
def tag(package_stream, owner):
    """Tag builds to target."""

    for pkg in package_stream:
        with pkg.destination["service"] as repo:
            # TODO: Potentialy duplicates packages (one per tag!)
            for tag in pkg.destination["tags"]:
                tagged = repo.tag_build(tag, pkg.metadata, owner=owner)
                yield attr.evolve(pkg, metadata=tagged)


@main.command()
@stream_processor(source="check")
def tested(package_stream):
    """Filter only packages that has been tested"""

    log = logger.getChild("tested")

    @lru_cache(maxsize=None)
    def test_set(service, tests):
        try:
            return {
                pkg.nvr  # FIXME ignoring arch and epoch
                for job in tests
                for pkg in service.tested_packages(job)
            }
        except UnknownJob as no_tests:
            log.warning(no_tests)
            return frozenset()

    def is_tested(package):
        result = package.metadata.nvr in test_set(
            service=package.source["service"], tests=tuple(package.source["tests"])
        )
        message = "{metadata}: {status}".format(
            metadata=package.metadata, status="tested" if result else "untested"
        )
        log.info(message)

        return result

    return filter(is_tested, package_stream)
