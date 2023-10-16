from sqlalchemy import inspect, insert

from huggy.models.non_recommendable_items import NonRecommendableItems


def create_non_recommendable_items(engine):
    if inspect(engine).has_table(NonRecommendableItems.__tablename__):
        NonRecommendableItems.__table__.drop(engine)
    NonRecommendableItems.__table__.create(bind=engine)

    with engine.connect() as conn:
        conn.execute(
            insert(NonRecommendableItems),
            [
                {"user_id": "111", "item_id": "isbn-1"},
                {"user_id": "112", "item_id": "isbn-3"},
            ],
        )
        conn.commit()
        conn.close()
