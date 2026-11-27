import random
from collections import defaultdict
from enum import StrEnum

from schemas.enriched_offer import EnrichedRecommendableOffer
from services.logger import logger


PRIMARY_MIXING_FEATURE = "search_group_name"
DEFAULT_SUB_MIXING_CONFIG = {
    "LIVRES": "gtl_id",
}


class GroupMergeStrategy(StrEnum):
    """Strategy used to flatten grouped offers back into a single list."""

    ROUND_ROBIN = "round_robin"
    SEQUENTIAL = "sequential"


def _group_offers_by_attribute(
    offers: list[EnrichedRecommendableOffer], attribute_name: str
) -> dict[str, list[EnrichedRecommendableOffer]]:
    """
    Groups a flat list of offers into a dictionary based on a specific attribute.

    Args:
        offers (list[EnrichedRecommendableOffer]): The list of offers to group.
        attribute_name (str): The name of the attribute to use as the grouping key
                              (e.g., 'search_group_name' or 'gtl_id').

    Returns:
        dict[str, list[EnrichedRecommendableOffer]]: A dictionary where keys are the attribute values
                                              and values are lists of matching offers.
                                              Defaults to the key 'OTHER' if the attribute is missing.
    """
    grouped_offers = defaultdict(list)

    for offer in offers:
        # Fallback to 'OTHER' if the targeted feature is None or an empty string
        group_key = getattr(offer, attribute_name, "OTHER") or "OTHER"
        grouped_offers[group_key].append(offer)

    return dict(grouped_offers)


def apply_offer_capping_per_group(
    offers: list[EnrichedRecommendableOffer],
    max_offers_per_group: int,
    attribute_name: str = PRIMARY_MIXING_FEATURE,
) -> list[EnrichedRecommendableOffer]:
    """
    Caps the number of offers sharing the same grouping attribute to at most `max_offers_per_group`.

    Guarantees no single group (e.g. a `search_group_name`, `gtl_id` or `gtl_label`) can flood the
    final playlist (e.g. 10 "Policier" books in a row). Offers are scanned in their current order
    (expected to already be ranked/scored), so the first `max_offers_per_group` offers encountered
    per group are kept; any later offer from an already-full group is set aside as a "leftover".

    To avoid needlessly shrinking the playlist when there isn't enough group diversity among the
    candidates, leftover offers are used to backfill the list back up to its original size, picked
    in their original (best-first) order regardless of their group. This means a group can end up
    with more than `max_offers_per_group` offers only if there is no other way to preserve the
    original candidate count.

    This function only caps; it does not reorder/interleave groups. Use
    `apply_offer_diversification_with_capping` (which calls this internally) for capping
    combined with group mixing/merging.

    Args:
        offers (list[EnrichedRecommendableOffer]): The ranked list of offers to cap (order matters).
        max_offers_per_group (int): The maximum ("K") number of offers allowed per group value.
        attribute_name (str): The attribute to group by - typically 'search_group_name', 'gtl_id'
                              or 'gtl_label'. Offers missing the attribute fall back to 'OTHER'.

    Returns:
        list[EnrichedRecommendableOffer]: The capped-and-backfilled list. Same length as `offers`
        unless there aren't enough leftover candidates to fully backfill.
    """
    if not offers or max_offers_per_group <= 0:
        return list(offers)

    group_counts: dict[str, int] = defaultdict(int)
    capped_offers: list[EnrichedRecommendableOffer] = []
    leftover_offers: list[EnrichedRecommendableOffer] = []

    for offer in offers:
        group_key = getattr(offer, attribute_name, "OTHER") or "OTHER"
        if group_counts[group_key] < max_offers_per_group:
            capped_offers.append(offer)
            group_counts[group_key] += 1
        else:
            leftover_offers.append(offer)

    # --- Backfill: top up with the best leftover offers to preserve the original total size ---
    missing_count = len(offers) - len(capped_offers)
    backfilled_count = 0
    if missing_count > 0 and leftover_offers:
        backfilled_count = min(missing_count, len(leftover_offers))
        capped_offers.extend(leftover_offers[:missing_count])

    logger.debug(
        "🧮 Offer capping per group applied.",
        extra={
            "attribute_name": attribute_name,
            "max_offers_per_group": max_offers_per_group,
            "input_offers": len(offers),
            "output_offers": len(capped_offers),
            "backfilled_count": backfilled_count,
        },
    )

    return capped_offers


def _sort_group_keys_by_priority(offer_groups: dict[str, list[EnrichedRecommendableOffer]]) -> list[str]:
    """
    Sorts group keys by priority, used by every group-merging strategy to decide which
    group should be favored first in the output.

    Priority order:
        1. By the number of items in the group (descending)
        2. By the maximum item_score found within the group (descending)

    Args:
        offer_groups (dict[str, list[EnrichedRecommendableOffer]]): The grouped offers to prioritize.

    Returns:
        list[str]: The group keys, ordered from highest to lowest priority.
    """
    return sorted(
        offer_groups.keys(),
        key=lambda key: (len(offer_groups[key]), max(offer.item_score or 0 for offer in offer_groups[key])),
        reverse=True,
    )


def _interleave_offer_groups_round_robin(
    offer_groups: dict[str, list[EnrichedRecommendableOffer]],
) -> list[EnrichedRecommendableOffer]:
    """
    Merges multiple grouped lists of offers using a Round-Robin algorithm.

    This ensures diversity in the final playlist by preventing multiple items
    from the same group from appearing consecutively. Groups are prioritized
    using `_sort_group_keys_by_priority`.

    Example Schema:
        Group A (Size 3): [A1, A2, A3]
        Group B (Size 2): [B1, B2]
        Group C (Size 1): [C1]

        Output sequence: A1 -> B1 -> C1 -> A2 -> B2 -> A3

    Args:
        offer_groups (dict[str, list[EnrichedRecommendableOffer]]): The grouped offers to interleave.

    Returns:
        list[EnrichedRecommendableOffer]: A single, flat, diversified list of offers.
    """
    interleaved_result = []

    # Initialize buckets based on the sorted priority
    active_buckets = [offer_groups[key] for key in _sort_group_keys_by_priority(offer_groups)]

    # Round-Robin extraction: take the first item of each bucket sequentially
    while active_buckets:
        for bucket in list(active_buckets):
            if not bucket:
                active_buckets.remove(bucket)
                continue

            # Pop the first element of the current bucket and append it to the result
            interleaved_result.append(bucket.pop(0))

    return interleaved_result


def _concatenate_offer_groups_sequential(
    offer_groups: dict[str, list[EnrichedRecommendableOffer]],
) -> list[EnrichedRecommendableOffer]:
    """
    Merges multiple grouped lists of offers by concatenating each group in full, one after
    another, instead of interleaving them. Offers sharing the same feature value therefore
    stay contiguous in the output. Groups are prioritized using `_sort_group_keys_by_priority`,
    same as `_interleave_offer_groups_round_robin`.

    Example Schema:
        Group A (Size 3): [A1, A2, A3]
        Group B (Size 2): [B1, B2]
        Group C (Size 1): [C1]

        Output sequence: A1 -> A2 -> A3 -> B1 -> B2 -> C1

    Args:
        offer_groups (dict[str, list[EnrichedRecommendableOffer]]): The grouped offers to concatenate.

    Returns:
        list[EnrichedRecommendableOffer]: A single, flat list of offers, grouped sequentially by feature.
    """
    return [offer for key in _sort_group_keys_by_priority(offer_groups) for offer in offer_groups[key]]


def _merge_offer_groups(
    offer_groups: dict[str, list[EnrichedRecommendableOffer]],
    merge_strategy: GroupMergeStrategy,
) -> list[EnrichedRecommendableOffer]:
    """
    Dispatches to the configured group-merging strategy.

    Args:
        offer_groups (dict[str, list[EnrichedRecommendableOffer]]): The grouped offers to merge.
        merge_strategy (GroupMergeStrategy): ROUND_ROBIN interleaves groups item-by-item;
                                             SEQUENTIAL concatenates each group in full.

    Returns:
        list[EnrichedRecommendableOffer]: A single, flat list of offers.
    """
    if merge_strategy == GroupMergeStrategy.SEQUENTIAL:
        return _concatenate_offer_groups_sequential(offer_groups)
    return _interleave_offer_groups_round_robin(offer_groups)


def _diversify_offer_groups(
    offers: list[EnrichedRecommendableOffer],
    sub_mixing_configuration: dict[str, str],
    merge_strategy: GroupMergeStrategy,
) -> list[EnrichedRecommendableOffer]:
    """
    Shared core of the diversification algorithm, used by both `apply_offer_diversification`
    and `apply_offer_diversification_with_capping`: groups offers by `PRIMARY_MIXING_FEATURE`,
    optionally sub-mixes specific categories, then merges every group back into a single flat
    list using the given `merge_strategy`.

    Args:
        offers (list[EnrichedRecommendableOffer]): The offers to diversify (already shuffled/capped if needed).
        sub_mixing_configuration (dict[str, str]): Mapping of category to its sub-feature
                                                   (e.g. {"LIVRES": "gtl_id"}).
        merge_strategy (GroupMergeStrategy): The strategy used to flatten groups back into a list.

    Returns:
        list[EnrichedRecommendableOffer]: The diversified playlist.
    """
    # --- Primary Grouping ---
    primary_offer_groups = _group_offers_by_attribute(offers, PRIMARY_MIXING_FEATURE)

    logger.debug(
        "🎨 Diversification: primary grouping done.",
        extra={
            "input_offers": len(offers),
            "group_count": len(primary_offer_groups),
            "groups": {k: len(v) for k, v in primary_offer_groups.items()},
        },
    )

    # --- Sub-mixing Phase (Specific Categories) ---
    for category, sub_attribute in sub_mixing_configuration.items():
        if category in primary_offer_groups:
            # Extract the specific category (e.g., 'LIVRES')
            category_specific_offers = primary_offer_groups[category]

            # Group it by its sub-feature (e.g., 'gtl_id')
            sub_grouped_offers = _group_offers_by_attribute(category_specific_offers, sub_attribute)

            # Merge the sub-groups back using the configured strategy
            primary_offer_groups[category] = _merge_offer_groups(sub_grouped_offers, merge_strategy)

    # --- Final Global Merge ---
    final_diversified_playlist = _merge_offer_groups(primary_offer_groups, merge_strategy)

    logger.debug(
        "✅ Diversification completed.",
        extra={"input_offers": len(offers), "output_offers": len(final_diversified_playlist)},
    )

    return final_diversified_playlist


def apply_offer_diversification(
    offers: list[EnrichedRecommendableOffer],
    sub_mixing_configuration: dict[str, str] | None = None,
    *,
    should_shuffle_initial_list: bool = False,
) -> list[EnrichedRecommendableOffer]:
    """
    Applies business rules to ensure the final recommendation playlist is diverse.

    This is the original/base entry point for the diversification phase. It performs a primary
    category mixing (e.g., mixing Books with Movies) and an optional sub-mixing for specific
    categories (e.g., mixing Manga with Sci-Fi within Books), interleaving groups Round-Robin.

    For a variant that additionally caps the number of offers per group and/or lets you
    configure the group-merging strategy, see `apply_offer_diversification_with_capping`.

    Args:
        offers (list[EnrichedRecommendableOffer]): The ranked list of offers.
        sub_mixing_configuration (dict[str, str] | None): Mapping of category to its sub-feature.
                                                          Defaults to DEFAULT_SUB_MIXING_CONFIG.
        should_shuffle_initial_list (bool): If True, randomly shuffles offers before grouping.
                                            Defaults to False.

    Returns:
        list[EnrichedRecommendableOffer]: The diversified playlist ready to be truncated and returned.
    """
    if not offers:
        return []

    # --- Initial Entropy / Shuffling ---
    if should_shuffle_initial_list:
        offers = list(offers)
        random.shuffle(offers)

    configuration = sub_mixing_configuration if sub_mixing_configuration is not None else DEFAULT_SUB_MIXING_CONFIG

    return _diversify_offer_groups(offers, configuration, GroupMergeStrategy.ROUND_ROBIN)


def apply_offer_diversification_with_capping(
    offers: list[EnrichedRecommendableOffer],
    max_offers_per_group: int,
    sub_mixing_configuration: dict[str, str] | None = None,
    *,
    should_shuffle_initial_list: bool = False,
    capping_attribute_name: str = PRIMARY_MIXING_FEATURE,
    merge_strategy: GroupMergeStrategy = GroupMergeStrategy.ROUND_ROBIN,
) -> list[EnrichedRecommendableOffer]:
    """
    Extended variant of `apply_offer_diversification` that additionally caps the number of
    offers sharing the same `capping_attribute_name` value (see `apply_offer_capping_per_group`),
    and lets you configure how groups are merged back into a flat list via `merge_strategy`:
        - GroupMergeStrategy.ROUND_ROBIN (default): interleaves groups item-by-item (see
          `_interleave_offer_groups_round_robin`), producing a varied, mixed-category feed.
        - GroupMergeStrategy.SEQUENTIAL: concatenates each group in full, one after another
          (see `_concatenate_offer_groups_sequential`), producing a feed where offers sharing
          the same feature value stay contiguous, ordered by group priority.

    Args:
        offers (list[EnrichedRecommendableOffer]): The ranked list of offers.
        max_offers_per_group (int): Caps the number of offers sharing the same
                                    `capping_attribute_name` value to at most this number
                                    (with backfill, see `apply_offer_capping_per_group`).
        sub_mixing_configuration (dict[str, str] | None): Mapping of category to its sub-feature.
                                                          Defaults to DEFAULT_SUB_MIXING_CONFIG.
        should_shuffle_initial_list (bool): If True, randomly shuffles offers before grouping.
                                            Defaults to False.
        capping_attribute_name (str): The attribute used for capping - typically
                                      'search_group_name', 'gtl_id' or 'gtl_label'.
                                      Defaults to PRIMARY_MIXING_FEATURE ('search_group_name').
        merge_strategy (GroupMergeStrategy): The strategy used to flatten groups back into a list.
                                             Defaults to GroupMergeStrategy.ROUND_ROBIN.

    Returns:
        list[EnrichedRecommendableOffer]: The diversified playlist ready to be truncated and returned.
    """
    if not offers:
        return []

    # --- 1. Initial Entropy / Shuffling ---
    if should_shuffle_initial_list:
        offers = list(offers)
        random.shuffle(offers)

    # --- 2. Capping Phase (at most K offers per group) ---
    offers = apply_offer_capping_per_group(offers, max_offers_per_group, capping_attribute_name)

    configuration = sub_mixing_configuration if sub_mixing_configuration is not None else DEFAULT_SUB_MIXING_CONFIG

    # --- 3. Grouping, Sub-mixing & Merging ---
    return _diversify_offer_groups(offers, configuration, merge_strategy)

