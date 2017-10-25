"""Utilities for interacting with file system"""

from io import TextIOWrapper
from itertools import chain
from pathlib import Path
from pkg_resources import resource_listdir, resource_stream
from typing import Iterator, TextIO, Sequence, Optional

from xdg.BaseDirectory import load_config_paths

from .. import RESOURCE_ID


def open_resource_files(
    root_dir: str,
    extension: str,
    *,
    encoding: str = 'utf-8',
    package: str = RESOURCE_ID
) -> Iterator[TextIO]:
    """Open package resources text files.

    Keyword arguments:
        root_dir: Path to the resource directory containing the files.
        extension: Extension of the files that should be opened.
        encoding: File encoding.
        package: The namespace to look for the resources in.

    Yields:
        Opened text streams.
    """

    base_names = resource_listdir(package, root_dir)
    paths = (
        '/'.join((root_dir, name))
        for name in base_names
        if name.endswith(extension)
    )
    binary_streams = (resource_stream(package, p) for p in paths)
    text_streams = (
        TextIOWrapper(bs, encoding=encoding)
        for bs in binary_streams
    )

    yield from text_streams


def open_config_files(
    glob: str,
    search_path_seq: Optional[Sequence[Path]] = None,
    *,
    encoding: str = 'utf-8'
) -> Iterator[TextIO]:
    """Open user configuration files.

    Keyword arguments:
        glob: The glob specifier matching the files to be opened.
        search_path_seq: The paths to search for the configuration files.
            Defaults to XDG configuration search path.
        encoding: File encoding.

    Yields:
        Opened text streams.
    """

    if search_path_seq is None:
        search_path_seq = map(Path, load_config_paths(RESOURCE_ID))

    conf_file_paths = chain.from_iterable(
        pth.glob(glob) for pth in search_path_seq,
    )
    conf_files = (pth.open(encoding=encoding) for pth in conf_file_paths)

    yield from conf_files
