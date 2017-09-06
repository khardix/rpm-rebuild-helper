"""Miscellaneous utility functions."""

from importlib import import_module
from itertools import chain
from io import TextIOWrapper
from operator import attrgetter
from pathlib import Path
from pkg_resources import resource_listdir, resource_stream
from typing import Any, Optional, Iterator
from typing import TextIO

import requests
from click import ClickException
from requests_file import FileAdapter
from xdg.BaseDirectory import load_config_paths


class SystemImportError(ClickException):
    """User-friendly indicator of missing system libraries."""

    def __init__(self, user_msg: str):
        """Provide a user-friendly message about missing import.

        Keyword arguments:
            user_msg: The message that should be presented to user.
        """

        super().__init__('System Import Error: {!s}'.format(user_msg))


def system_import(module_name: str, *attribute_names) -> Any:
    """Try to import system-installed package, with user warning on failure.

    Keyword arguments:
        module_name: The name of the system module to be imported.
        attribute_names: Names from the system module to be imported directly.

    Returns:
        If no attribute_names were specified, returns the module itself.
        If at least one attribute name were provided, returns
            a tuple of the attributes themselves.

    Raises:
        SystemImportError: When the module is not available, or requested
            attribute is not present within the module.
    """

    try:
        module = import_module(module_name)

    except ImportError:
        message = 'System module "{}" is not available'.format(module_name)
        raise SystemImportError(message)

    if not attribute_names:
        return module

    try:
        return attrgetter(*attribute_names)(module)

    except AttributeError as err:
        message = 'System module "{module}" does not provide "{attribute}"'
        raise SystemImportError(message.format(
            module=module_name,
            attribute=err.args[0],
        ))


def default_requests_session(session: Optional[requests.Session] = None):
    """Create a requests.Session with suitable default values.

    This function is intended for use by functions that can utilize
    provided session, but do not require it.

    Example::
        def download(url: str, *, session: Optional[requests.Session] = None):
            # Use provided session if any, or create new session
            session = default_requests_session(session)

    Keyword arguments:
        session: If not None, the session is passed unchanged.
                 If None, create new session.
    """

    if session is not None:
        return session

    session = requests.Session()

    # Add local file adapter
    session.mount('file://', FileAdapter())

    return session


def open_resource_files(
    root_dir: str,
    extension: str,
    *,
    encoding: str = 'utf-8',
    package: str = __package__
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
    extension: str,
    *,
    encoding: str = 'utf-8'
) -> Iterator[TextIO]:
    """Open user configuration files.

    Keyword arguments:
        extension: Extension of the files that should be opened.
        encoding: File encoding.

    Yields:
        Opened text streams.
    """

    conf_dirs = map(Path, load_config_paths(__package__))
    conf_file_paths = chain.from_iterable(
        pth.glob('*{}'.format(extension)) for pth in conf_dirs
    )
    conf_files = (pth.open(encoding=encoding) for pth in conf_file_paths)

    yield from conf_files
