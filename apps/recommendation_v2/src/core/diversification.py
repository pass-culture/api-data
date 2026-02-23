import random
from collections import defaultdict

from models.offer import RecommendableOffers


PRIMARY_MIXING_FEATURE = "search_group_name"
DEFAULT_SUB_MIXING_CONFIG = {
    "LIVRES": "gtl_id",
}


def _group_offers_by_attribute(
    offers: list[RecommendableOffers], attribute_name: str
) -> dict[str, list[RecommendableOffers]]:
    """
    Groups a flat list of offers into a dictionary based on a specific attribute.

    Args:
        offers (list[RecommendableOffers]): The list of offers to group.
        attribute_name (str): The name of the attribute to use as the grouping key
                              (e.g., 'search_group_name' or 'gtl_id').

    Returns:
        dict[str, list[RecommendableOffers]]: A dictionary where keys are the attribute values
                                              and values are lists of matching offers.
                                              Defaults to the key 'OTHER' if the attribute is missing.
    """
    grouped_offers = defaultdict(list)

    for offer in offers:
        # Fallback to 'OTHER' if the targeted feature is None or an empty string
        group_key = getattr(offer, attribute_name, "OTHER") or "OTHER"
        grouped_offers[group_key].append(offer)

    return dict(grouped_offers)


def _interleave_offer_groups_round_robin(
    offer_groups: dict[str, list[RecommendableOffers]],
) -> list[RecommendableOffers]:
    """
    Merges multiple grouped lists of offers using a Round-Robin algorithm.

    This ensures diversity in the final playlist by preventing multiple items
    from the same group from appearing consecutively. Groups are prioritized
    by their size, and secondarily by the highest score within the group.

    Example Schema:
        Group A (Size 3): [A1, A2, A3]
        Group B (Size 2): [B1, B2]
        Group C (Size 1): [C1]

        Output sequence: A1 -> B1 -> C1 -> A2 -> B2 -> A3

    Args:
        offer_groups (dict[str, list[RecommendableOffers]]): The grouped offers to interleave.

    Returns:
        list[RecommendableOffers]: A single, flat, diversified list of offers.
    """
    interleaved_result = []

    # Sort the group keys:
    # 1. By the number of items in the group (descending)
    # 2. By the maximum item_score found within the group (descending)
    sorted_group_keys = sorted(
        offer_groups.keys(),
        key=lambda key: (len(offer_groups[key]), max(offer.item_score or 0 for offer in offer_groups[key])),
        reverse=True,
    )

    # Initialize buckets based on the sorted priority
    active_buckets = [offer_groups[key] for key in sorted_group_keys]

    # Round-Robin extraction: take the first item of each bucket sequentially
    while active_buckets:
        for bucket in list(active_buckets):
            if not bucket:
                active_buckets.remove(bucket)
                continue

            # Pop the first element of the current bucket and append it to the result
            interleaved_result.append(bucket.pop(0))

    return interleaved_result


def apply_offer_diversification(
    offers: list[RecommendableOffers],
    sub_mixing_configuration: dict[str, str] | None = None,
    *,
    should_shuffle_initial_list: bool = False,
) -> list[RecommendableOffers]:
    """
    Applies business rules to ensure the final recommendation playlist is diverse.

    This acts as the main entry point for the diversification phase. It performs
    both a primary category mixing (e.g., mixing Books with Movies) and an optional
    sub-mixing for specific categories (e.g., mixing Manga with Sci-Fi within Books).

    Args:
        offers (list[RecommendableOffers]): The ranked list of offers.
        sub_mixing_configuration (dict[str, str] | None): Mapping of category to its sub-feature.
                                                          Defaults to DEFAULT_SUB_MIXING_CONFIG.
        should_shuffle_initial_list (bool): If True, randomly shuffles offers before grouping.
                                            Defaults to False.

    Returns:
        list[RecommendableOffers]: The diversified playlist ready to be truncated and returned.
    """
    if not offers:
        return []

    # --- 1. Initial Entropy / Shuffling ---
    if should_shuffle_initial_list:
        offers = list(offers)
        random.shuffle(offers)

    configuration = sub_mixing_configuration if sub_mixing_configuration is not None else DEFAULT_SUB_MIXING_CONFIG

    # --- 2. Primary Grouping ---
    primary_offer_groups = _group_offers_by_attribute(offers, PRIMARY_MIXING_FEATURE)

    # --- 3. Sub-mixing Phase (Specific Categories) ---
    for category, sub_attribute in configuration.items():
        if category in primary_offer_groups:
            # Extract the specific category (e.g., 'LIVRES')
            category_specific_offers = primary_offer_groups[category]

            # Group it by its sub-feature (e.g., 'gtl_id')
            sub_grouped_offers = _group_offers_by_attribute(category_specific_offers, sub_attribute)

            # Interleave the sub-groups
            mixed_category_offers = _interleave_offer_groups_round_robin(sub_grouped_offers)

            # Replace the original flat list with the internally diversified one
            primary_offer_groups[category] = mixed_category_offers

    # --- 4. Final Global Interleaving ---
    final_diversified_playlist = _interleave_offer_groups_round_robin(primary_offer_groups)

    return final_diversified_playlist
