"""Miscellaneous utility functions."""

from importlib import import_module
from operator import attrgetter
from typing import Any, Optional

import requests
from click import ClickException
from requests_file import FileAdapter


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
