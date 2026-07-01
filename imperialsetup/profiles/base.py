from __future__ import annotations

from copy import deepcopy

from ..blueprint import CATEGORIES, ROLE_SPECS


def base_profile() -> dict:
    categories = deepcopy(CATEGORIES)
    for category in categories:
        if category.get("name") == "💻 DEVELOPMENT":
            category["channels"] = [
                channel
                for channel in category.get("channels", [])
                if channel.get("name") != "arcaea-viewer"
            ]
    return {"roles": deepcopy(ROLE_SPECS), "categories": categories}
