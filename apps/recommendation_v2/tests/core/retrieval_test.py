from core.retrieval import _build_similar_offer_search_filters
from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum


def test_build_similar_offer_search_filters_returns_empty_and_list_when_no_filters_provided():
    """When no filters are provided, should return an empty $and list."""
    result = _build_similar_offer_search_filters()

    assert result == {"$and": []}


def test_build_similar_offer_search_filters_with_single_filter_type():
    """When one filter type is provided, should return correct structure."""
    result = _build_similar_offer_search_filters(categories=[CategoryEnum.LIVRE, CategoryEnum.INSTRUMENT])

    assert result == {"$and": [{"category": {"$in": ["LIVRE", "INSTRUMENT"]}}]}


def test_build_similar_offer_search_filters_with_all_parameters_combined():
    """When all filter types are provided, should combine them in $and list."""
    result = _build_similar_offer_search_filters(
        categories=[CategoryEnum.LIVRE],
        subcategories=[SubcategoryEnum.ABO_CONCERT],
        search_group_names=[SearchGroupNameEnum.CONCERTS_FESTIVALS, SearchGroupNameEnum.CARTES_JEUNES],
    )

    assert result == {
        "$and": [
            {"category": {"$in": ["LIVRE"]}},
            {"subcategory_id": {"$in": ["ABO_CONCERT"]}},
            {"search_group_name": {"$in": ["CONCERTS_FESTIVALS", "CARTES_JEUNES"]}},
        ]
    }


def test_build_similar_offer_search_filters_ignores_empty_lists():
    """When empty lists are provided, should not include them in filters."""
    result = _build_similar_offer_search_filters(
        categories=[],
        subcategories=[SubcategoryEnum.ABO_CONCERT],
        search_group_names=[],
    )

    assert result == {"$and": [{"subcategory_id": {"$in": ["ABO_CONCERT"]}}]}
