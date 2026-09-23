"""
apps.accounts.views — split into one module per feature area (see the
sibling files in this package) so no single file holds the whole app's
view surface. This __init__ re-exports everything so every existing
caller — urls.py, the sibling views_*.py files, serializers.py — keeps
working unchanged via `from apps.accounts.views import X`.

Originally one 7,769-line views.py; split mechanically (no behavior
change) into: shared.py (private helper functions used across modules)
plus one file per domain area (auth, roles_permissions, org_structure,
smtp_settings, email_templates, documents, company, employees_list,
employees_detail, employees_actions, onboarding_wizard, onboarding_config,
onboarding_documents, custom_field_files, onboarding_approval, my_profile,
hr_manager_lists, approval_workflow, bulk_import).
"""

from .shared import *  # noqa: F401,F403

from .auth import *  # noqa: F401,F403
from .roles_permissions import *  # noqa: F401,F403
from .org_structure import *  # noqa: F401,F403
from .smtp_settings import *  # noqa: F401,F403
from .email_templates import *  # noqa: F401,F403
from .documents import *  # noqa: F401,F403
from .company import *  # noqa: F401,F403
from .employees_list import *  # noqa: F401,F403
from .employees_detail import *  # noqa: F401,F403
from .employees_actions import *  # noqa: F401,F403
from .onboarding_wizard import *  # noqa: F401,F403
from .onboarding_config import *  # noqa: F401,F403
from .onboarding_documents import *  # noqa: F401,F403
from .custom_field_files import *  # noqa: F401,F403
from .onboarding_approval import *  # noqa: F401,F403
from .my_profile import *  # noqa: F401,F403
from .hr_manager_lists import *  # noqa: F401,F403
from .approval_workflow import *  # noqa: F401,F403
from .bulk_import import *  # noqa: F401,F403
