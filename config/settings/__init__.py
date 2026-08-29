from .base import *  # noqa: F401,F403

import os
if os.environ.get("DJANGO_ENV") == "production":
    from .production import *  # noqa: F401,F403
else:
    from .development import *  # noqa: F401,F403
