"""Utilities related to the import system."""

import sys
from contextlib import ContextDecorator
from importlib import import_module
from operator import attrgetter
from pathlib import Path
from typing import Any


class system_environment(ContextDecorator):
    """Use only system site-packages, ignoring any virtual environments.

    When within this context, the `sys.path` variable is modified
    to ignore packages installed within a virtual environment
    and to use the system (global) installed packages instead.

    Use sparingly and with care.
    """

    #: Relative path from library directory to site-packages
    _SITEDIR: Path = Path(
        f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages"
    )
    #: Noarch library directory
    _LIBRARY_NOARCH: Path = Path("lib")
    #: Architecture-dependent library direcotry
    _LIBRARY_ARCH: Path = Path("lib32" if sys.maxsize < 2 ** 32 else "lib64")

    def __init__(self):
        """Prepare path backup stack for this context."""
        super().__init__()

        self.path_stack = []

    def __enter__(self):
        """Replace paths of virtual environment with system ones in `sys.path`."""

        self.path_stack.append(sys.path)

        in_virtual_env = sys.prefix != sys.base_prefix
        if in_virtual_env:
            # Strip paths of virtual environment from sys.path
            modified = [pth for pth in sys.path if not pth.startswith(sys.prefix)]
            # Append paths of system environment
            modified.append(str(sys.base_prefix / self._LIBRARY_NOARCH / self._SITEDIR))
            modified.append(str(sys.base_prefix / self._LIBRARY_ARCH / self._SITEDIR))
            # Use the system environment
            sys.path = modified

    def __exit__(self, *_exc_info):
        """Restore original `sys.path`"""
        sys.path = self.path_stack.pop()


class SystemImportError(ImportError):
    """User-friendly indicator of missing system libraries."""

    def __init__(self, user_msg: str):
        """Provide a user-friendly message about missing import.

        Keyword arguments:
            user_msg: The message that should be presented to user.
        """

        super().__init__("System Import Error: {!s}".format(user_msg))


@system_environment()
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
