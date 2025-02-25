import collections
import random

import numpy as np
from huggy.schemas.recommendable_offer import RankedOffer
from huggy.utils.env_vars import NUMBER_OF_RECOMMENDATIONS


def order_offers_by_score_and_diversify_features(
    scored_offers: list[RankedOffer],
    score_column="offer_rank",
    score_order_ascending=True,
    shuffle_recommendation=None,
    feature="subcategory_id",
    nb_reco_display=NUMBER_OF_RECOMMENDATIONS,
    is_submixing=False,
    submixing_feature_dict=None,
) -> list[RankedOffer]:
    """
    Group scored_offers by feature.
    Order offer groups by decreasing number of offers in each group and decreasing maximal score.
    Order each offers within a group by increasing score.
    Sort offers by taking the last offer of each group (maximum score), by decreasing size of group.
    Return only the ids of these sorted offers.
    score_order_ascending is False, score = the higher the better

    """

    diversified_offers = []
    if shuffle_recommendation:
        for recommendation in scored_offers:
            setattr(recommendation, score_column, random.random())

    offers_by_feature = _get_offers_grouped_by_feature(
        scored_offers, feature
    )  # here we group offers by cat (and score)

    to_submixed_data = {}
    if submixing_feature_dict is not None:
        for submixed_subcat in submixing_feature_dict:
            if submixed_subcat in offers_by_feature:
                to_submixed_data[submixed_subcat] = offers_by_feature[submixed_subcat]

    offers_by_feature_ordered_by_frequency = collections.OrderedDict(
        sorted(
            offers_by_feature.items(),
            key=lambda x: _get_number_of_offers_and_max_score_by_feature(
                x,
                score_column=score_column,
                score_order_ascending=score_order_ascending,
            ),
            reverse=not score_order_ascending,
        )
    )

    for offer_feature in offers_by_feature_ordered_by_frequency:
        offers_by_feature_ordered_by_frequency[offer_feature] = sorted(
            offers_by_feature_ordered_by_frequency[offer_feature],
            key=lambda k: getattr(k, score_column),
            reverse=score_order_ascending,
        )
    if (not is_submixing) and (len(to_submixed_data) > 0):
        is_submixing = True
        for subcat_to_mix in to_submixed_data:
            submixed_data = order_offers_by_score_and_diversify_features(
                to_submixed_data[subcat_to_mix],
                score_column=score_column,
                score_order_ascending=score_order_ascending,
                shuffle_recommendation=None,
                feature=submixing_feature_dict[subcat_to_mix],
                nb_reco_display=len(to_submixed_data[subcat_to_mix]),
                is_submixing=is_submixing,
            )
            submixed_data.reverse()
            offers_by_feature_ordered_by_frequency[subcat_to_mix] = submixed_data
    offers_by_feature_length = np.sum(
        [len(offer_by_feature) for offer_by_feature in offers_by_feature.values()]
    )
    while len(diversified_offers) != offers_by_feature_length:
        # here we pop one offer of eachsubcat
        for offer_feature in offers_by_feature_ordered_by_frequency:
            if offers_by_feature_ordered_by_frequency[offer_feature]:
                diversified_offers.append(
                    offers_by_feature_ordered_by_frequency[offer_feature].pop()
                )
        if len(diversified_offers) >= nb_reco_display:
            break

    return diversified_offers


def _get_offers_grouped_by_feature(
    scored_offers: list[RankedOffer], feature="subcategory_id"
) -> dict:
    offers_by_feature = {}
    product_ids = set()
    for offer in scored_offers:
        offer_feature = getattr(offer, feature)
        offer_product_id = offer.item_id
        if offer_feature in offers_by_feature:  # Here we filter subcat
            if offer_product_id not in product_ids:
                offers_by_feature[offer_feature].append(offer)
                product_ids.add(offer_product_id)
        else:
            offers_by_feature[offer_feature] = [offer]
    return offers_by_feature


def _get_number_of_offers_and_max_score_by_feature(
    feature_and_offers: tuple,
    score_column: str = "score",
    *,
    score_order_ascending: bool,
) -> tuple:
    if score_order_ascending:
        sum_score = min(
            [getattr(offer, score_column) for offer in feature_and_offers[1]]
        )
    else:
        sum_score = max(
            [getattr(offer, score_column) for offer in feature_and_offers[1]]
        )
    return sum_score, len(feature_and_offers[1])
