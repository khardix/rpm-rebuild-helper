"""Loading of configuration files from package and file system"""

import fnmatch
from collections import ChainMap
from contextlib import ExitStack
from io import TextIOWrapper
from itertools import chain
from typing import Callable, Iterator, Mapping, Optional, Sequence, TextIO
from pathlib import Path
from pkg_resources import resource_listdir, resource_stream

import toml
from xdg.BaseDirectory import load_config_paths

from .. import RESOURCE_ID

#: Path from package root to bundled configuration
RESOURCE_ROOT_DIR = "conf.d"


def open_matching_resources(
    glob: str,
    *,
    package: str = RESOURCE_ID,
    root_dir: str = RESOURCE_ROOT_DIR,
    encoding: str = "utf-8",
) -> Iterator[TextIO]:
    """Open bundled resources specified by a glob.

    Keyword arguments:
        glob: The glob describing the files to open.
        package: The package to search.
        root_dir: Path from the package root to searched directory.
        encoding: Expected stream encoding.

    Yields:
        Open streams for found resources. It is the caller responsibility to close them.
    """

    candidate_list = resource_listdir(package, root_dir)
    match_iter = fnmatch.filter(candidate_list, glob)

    for name in match_iter:
        path = "/".join((root_dir, name))
        binary_stream = resource_stream(package, path)

        yield TextIOWrapper(binary_stream, encoding=encoding)


def open_matching_files(
    glob: str,
    *,
    search_path_seq: Optional[Sequence[Path]] = None,
    encoding: str = "utf-8",
) -> Iterator[TextIO]:
    """Open (configuration) files matching a glob in searched directories.

    Keyword arguments:
        glob: The glob describing the files to open.
        search_path_seq: File system directories that are searched for the files to open.
            Defaults to XDG configuration search path (env:`XDG_CONFIG_DIRS`).
        encoding: Expected file encoding.

    Yields:
        Open streams for found files. It is the caller responsibility to close them.
    """

    if search_path_seq is None:
        search_path_seq = list(map(Path, load_config_paths(RESOURCE_ID)))

    match_iter = chain.from_iterable(
        directory.glob(glob) for directory in search_path_seq
    )
    yield from (match.open(encoding=encoding) for match in match_iter)


def load_matching_configuration(
    glob: str, *, interpret: Callable[[TextIO], Mapping] = toml.load
) -> ChainMap:
    """Load configuration from all matching files/resources.

    The configuration is merged to single Mapping, with specific configuration
    overriding more generic one.

    Keyword arguments:
        glob: The glob describing the configuration files/resources to open.
        interpret: Converter from text to Python data types.

    Returns:
        Configuration data merged into single ChainMap.
    """

    with ExitStack() as to_close:
        file_iter = open_matching_files(glob)
        resource_iter = open_matching_resources(glob)
        stream_iter = map(to_close.enter_context, chain(file_iter, resource_iter))
        data_iter = map(interpret, stream_iter)

        return ChainMap(*data_iter)
