"""Redis-kalitlarni quruvchi YAGONA modul (reja §4: "bitta helper-modul quradi").
Boshqa joyda f-string bilan tenant-kalit yasash TAQIQLANADI — grep bilan tekshiriladi.
"""

import uuid


def live_channel(org_id: uuid.UUID) -> str:
    """Org'ning jonli-oqim pub/sub kanali (nuqta + site_enter/site_exit hodisalari)."""
    return f"t:{org_id}:live"


def last_loc_hash(org_id: uuid.UUID) -> str:
    """HSET: field=user_id → json {lat, lon, ts, accuracy_m, battery, site_id}."""
    return f"t:{org_id}:loc:last"


def presence_zset(org_id: uuid.UUID) -> str:
    """ZSET: member=user_id, score=oxirgi nuqta epoch. Online = score >= now-120s."""
    return f"t:{org_id}:presence"


def sp_state_hash(org_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """Site-presence gisterezis holati (cur_site, row_id, cand_site, in_count, out_since)."""
    return f"t:{org_id}:sp:{user_id}"
