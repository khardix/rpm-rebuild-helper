"""Compatibility layer for system DNF"""
from typing import Callable
from typing import Optional
from typing import TYPE_CHECKING

from pkg_resources import parse_version

from ...util import system_import

if TYPE_CHECKING:
    import dnf
else:
    dnf = system_import("dnf")

# Types
BasePatch = Callable[[dnf.Base], dnf.Base]

# Constants
DNF_VERSION = parse_version(dnf.__version__)


def make_compatible(base: dnf.Base) -> dnf.Base:
    """Applies relevant workarounds to dnf.Base.

    See the dedicated functions for details.

    Keyword arguments:
        base: The dnf.Base to monkeypatch.

    Returns:
        Adjusted base.
    """

    repo_baseurl_make_native(base)

    return base


# Helper meta-functions


def IDENTITY(base: dnf.Base, *args, **_kwargs):
    """Replacement function for functions that should do nothing.

    Returns: Unchanged base.
    """

    return base


def in_version(minimal: Optional[str] = None, maximal: Optional[str] = None):
    """Applies a function if the DNF_VERSION is in specified range.

    When the DNF_VERSION is not in range,
    the decorated function is replaced with an "identity"
    -- a function that just returns its first argument unchanged.

    Keyword arguments:
        minimal: The minimal version (inclusive) to apply the decorated function.
        maximal: The maximal version (exclusive) to apply the decorated function.

    Returns:
        Decorator that replaces unsuitable functions with identity ones.
    """

    fits_min = True if minimal is None else parse_version(minimal) <= DNF_VERSION
    fits_max = True if maximal is None else parse_version(maximal) > DNF_VERSION
    version_fits = fits_min and fits_max

    def decorator(func: BasePatch) -> BasePatch:
        if version_fits:
            return func
        else:
            return IDENTITY

    return decorator


# Workarounds


@in_version(minimal="3.0.0")
def repo_baseurl_make_native(base: dnf.Base) -> dnf.Base:
    """Ensure that baseurl in each repository is a list of Python strings.

    Workaround: rhbz#1649284 -- Package.remote_location fails with AttributeError
    """

    class BaseurlRepoProxy:
        def __init__(self, repo):
            self.__repo = repo

        def __getattr__(self, name):
            return getattr(self.__repo, name)

        @property
        def baseurl(self):
            return list(map(str, self.__repo.baseurl))

    for name, repo in base.repos.items():
        base.repos[name] = BaseurlRepoProxy(repo)

    return base
