"""Utilities related to the import system."""

from importlib import import_module
from operator import attrgetter
from typing import Any


class SystemImportError(ImportError):
    """User-friendly indicator of missing system libraries."""

    def __init__(self, user_msg: str):
        """Provide a user-friendly message about missing import.

        Keyword arguments:
            user_msg: The message that should be presented to user.
        """

        super().__init__("System Import Error: {!s}".format(user_msg))


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

    except ImportError as err:
        message = 'System module "{}" is not available'.format(module_name)
        raise SystemImportError(message) from err

    if not attribute_names:
        return module

    try:
        return attrgetter(*attribute_names)(module)

    except AttributeError as err:
        message = 'System module "{module}" does not provide "{attribute}"'
        raise SystemImportError(
            message.format(module=module_name, attribute=err.args[0])
        ) from err
