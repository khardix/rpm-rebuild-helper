"""Run time configuration loading and storage"""

from collections import ChainMap, defaultdict
from contextlib import ExitStack
from itertools import chain
from operator import methodcaller
from pathlib import Path
from typing import Sequence, Optional

import pytoml as toml

from .service import Registry, InitializerMap, INIT_REGISTRY
from .validation import MAIN_CONF_SCHEMA, validate_raw
from ..util import open_resource_files, open_config_files

#: Main configuration base name
CONF_BASE_NAME = 'config.toml'
#: Extension for service files
SERVICE_EXT = '.service.toml'


def load_configuration(
    base_name: str = CONF_BASE_NAME,
    search_path_seq: Optional[Sequence[Path]] = None
) -> dict:
    """Load, validate and merge the application configuration.

    Application configuration is two-level nested dictionary
    (similar to INI files).

    Keyword arguments:
        base_name: The base name of the configuration files to load.
        search_path_seq: Priority sequence of paths to search for the
            configuration files. Defaults to XDG configuration search path.

    Returns:
        Validated and merged configuration.
    """

    result = defaultdict(ChainMap)

    # Gather both bundled and user configuration
    user_file_iter = open_config_files(base_name, search_path_seq)
    bundle_file_iter = open_resource_files('conf.d', base_name)
    file_iter = chain(user_file_iter, bundle_file_iter)

    # Open, read and merge the configuration
    with ExitStack() as opened:
        file_iter = map(opened.enter_context, file_iter)
        content_iter = map(toml.load, file_iter)
        content_iter = (
            validate_raw(c, schema=MAIN_CONF_SCHEMA) for c in content_iter
        )
        section_iter = chain.from_iterable(
            map(methodcaller('items'), content_iter)
        )

        for section, values in section_iter:
            result[section].maps.append(values)

    return result


def load_services(
    extension: str = SERVICE_EXT,
    search_path_seq: Optional[Sequence[Path]] = None,
    *,
    init_registry: InitializerMap = INIT_REGISTRY
) -> Registry:
    """Load, validate and sort service definitions.

    Keyword arguments:
        extension: The extension of the service files.
        search_path_seq: Priority sequence of paths to search for the
            configuration files. Defaults to XDG configuration search path.

    Returns:
        Filled service.Registry.
    """

    name_glob = '*{extension}'.format(extension=extension)

    user_service_iter = open_config_files(name_glob, search_path_seq)
    bundle_service_iter = open_resource_files('conf.d', extension)
    service_iter = chain(user_service_iter, bundle_service_iter)

    with ExitStack() as opened:
        service_iter = map(opened.enter_context, service_iter)
        content_iter = list(map(toml.load, service_iter))

        return Registry.from_merged(
            *content_iter,
            init_registry=init_registry,
        )
