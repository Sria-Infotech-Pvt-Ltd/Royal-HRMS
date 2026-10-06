"""
platform_core models, split by phase/concern (one file per Phase — see
each submodule's own docstring). All models are re-exported here so
Django's app loading (which imports `apps.platform_core.models` as one
module) discovers every model regardless of which file it lives in.
"""
from .phase1 import *  # noqa: F401,F403
from .fields import *  # noqa: F401,F403
from .forms import *  # noqa: F401,F403
from .custom_objects import *  # noqa: F401,F403
from .lists import *  # noqa: F401,F403
from .attachments import *  # noqa: F401,F403
from .imports import *  # noqa: F401,F403
