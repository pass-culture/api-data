from tests.db.enriched_user import (
    create_enriched_user_mv,
    create_enriched_user_mv_old,
    create_enriched_user_mv_tmp,
)
from tests.db.iris_france import (
    # create_iris_france,
    create_iris_france_mv,
    create_iris_france_mv_old,
    create_iris_france_mv_tmp,
)
from tests.db.non_recommendable_items import create_non_recommendable_items
from tests.db.recommendable_offers_raw import (
    create_item_ids_mv,
    create_recommendable_offers_raw,
    create_recommendable_offers_raw_mv,
    create_recommendable_offers_raw_mv_old,
    create_recommendable_offers_raw_mv_tmp,
)

__all__ = [
    "create_enriched_user_mv",
    "create_enriched_user_mv_old",
    "create_enriched_user_mv_tmp",
    "create_iris_france_mv",
    "create_iris_france_mv_old",
    "create_iris_france_mv_tmp",
    "create_item_ids_mv",
    "create_non_recommendable_items",
    "create_recommendable_offers_raw",
    "create_recommendable_offers_raw_mv",
    "create_recommendable_offers_raw_mv_old",
    "create_recommendable_offers_raw_mv_tmp",
]
