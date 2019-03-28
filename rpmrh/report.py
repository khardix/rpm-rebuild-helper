"""Serialization and deserialization of processing results."""
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import TextIO

import attr
from ruamel import yaml
from typing_extensions import Final

from .rpm import PackageLike
from .rpm import SoftwareCollection

# Collection -> Distribution -> [Package]
ResultDict = Dict[Optional[SoftwareCollection], Dict[str, List[PackageLike]]]


class _YAMLTag(str, Enum):
    """Canonical names of YAML tags used below.

    The values are taken from the PyYAML/ruamel.yaml documentation and source code.

    This enum is *not* exhaustive.
    """

    # YAML primitives
    NULL = "tag:yaml.org,2002:null"
    STRING = "tag:yaml.org,2002:str"
    # Additional python builtins
    PATH = "!!python/object:pathlib.Path"


class _SafeTypeConverter(yaml.YAML):
    """A type registry and YAML converter for Python classes.

    Only classes explicitly marked as de/serializable can be converted.
    """

    @staticmethod
    def _represent_none(representer: yaml.Representer, _data: None) -> yaml.Node:
        """Represent `None` as ``~``."""

        return representer.represent_scalar(_YAMLTag.NULL, "~")

    @staticmethod
    def _represent_path(representer: yaml.Representer, path: Path) -> yaml.Node:
        """Represent pathlib.Path as string."""

        return representer.represent_scalar(_YAMLTag.PATH, str(path))

    @staticmethod
    def _construct_path(constructor: yaml.Constructor, node: yaml.ScalarNode) -> Path:
        """Construct pathlib.Path instance from string."""

        return Path(constructor.construct_scalar(node))

    def __init__(self) -> None:
        """Configure the instance with canonical serialization style."""

        super().__init__(typ="rt")  # enable round-trip conversion by default

        self.explicit_start = self.explicit_end = True  # make yamllint happy
        self.default_flow_style = False  # do not pack list items
        self.indent(mapping=2, sequence=4, offset=2)

        # Add additional representers and constructors
        self.representer.add_representer(type(None), self._represent_none)
        self.representer.add_multi_representer(Path, self._represent_path)
        self.constructor.add_constructor(_YAMLTag.PATH, self._construct_path)


#: Known result types
TYPE_REGISTRY: Final = _SafeTypeConverter()


@attr.s(slots=True, frozen=True)
class Container:
    """Serializable and iterable result container."""

    #: Mapping of successfully processed items (packages)
    result: ResultDict = attr.ib(factory=dict)

    def insert_package(self, package: PackageLike) -> None:
        """Insert package to it's canonical place."""

        scl_dict = self.result.setdefault(package.scl, {})
        dist_list = scl_dict.setdefault(str(package.metadata.dist), [])
        dist_list.append(package)

    def as_yaml(
        self, output: Optional[TextIO] = None, *, registry: yaml.YAML = TYPE_REGISTRY
    ) -> Optional[str]:
        """Converts the container into it's YAML representation.

        Arguments:
            output: If specified, the YAML is written into that stream.
                In that case, None is returned.

        Keyword arguments:
            registry: The type registry/converter to use for serialization [default: `TYPE_REGISTRY`]

        Returns:
            str: When output *is not* specified; the YAML representation as a string.
            None: When output *is* specified.
        """

        buffer = StringIO()

        if output is None:
            output = buffer

        registry.dump(attr.asdict(self, recurse=False), output)

        if output is buffer:
            return buffer.getvalue()
        else:
            return None
