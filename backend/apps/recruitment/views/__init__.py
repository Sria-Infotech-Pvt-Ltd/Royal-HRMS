"""
apps.recruitment.views — split into one module per feature area (see the
sibling files in this package) so no single file holds the whole app's
view surface. This __init__ re-exports everything so every existing
caller — urls.py, apps/recruitment/tasks.py — keeps working unchanged via
`from apps.recruitment.views import X`.

Originally one 2,340-line views.py; split mechanically (no behavior
change) into: shared.py (private helper functions used across modules)
plus one file per domain area (candidates_core, candidate_status,
candidate_review_email, candidate_portal, referrals, bulk_import).
"""

from .shared import *  # noqa: F401,F403

from .candidates_core import *  # noqa: F401,F403
from .candidate_status import *  # noqa: F401,F403
from .candidate_review_email import *  # noqa: F401,F403
from .candidate_portal import *  # noqa: F401,F403
from .referrals import *  # noqa: F401,F403
from .bulk_import import *  # noqa: F401,F403
