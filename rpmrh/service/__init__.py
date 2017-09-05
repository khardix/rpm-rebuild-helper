# Collapse configuration namespace
from .configuration import InitializerMap  # noqa: F401
from .configuration import INIT_REGISTRY as REGISTRY  # noqa: F401
from .configuration import register, instantiate  # noqa: F401
from .configuration import Index, IndexGroup  # noqa: F401

# Import all services on package import
from . import abc, dnf, koji  # noqa: F401
