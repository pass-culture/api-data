from sqlalchemy import Column, String, Integer, DateTime, Float, ForeignKey, inspect

from huggy.utils.database import Base


class User(Base):
    """Database model of enriched_user table.
    This table is used to get informations about the user calling the API."""

    __tablename__ = "enriched_user"
    user_id = Column(String(256), primary_key=True)
    user_deposit_creation_date = Column(DateTime(timezone=True))
    user_birth_date = Column(DateTime(timezone=True))
    user_deposit_initial_amount = Column(Float)
    user_theoretical_remaining_credit = Column(Float)
    booking_cnt = Column(Integer)
    consult_offer = Column(Integer)
    has_added_offer_to_favorites = Column(Integer)


class UserMv(User):
    """Database model of enriched_user table.
    This table is used to get informations about the user calling the API."""

    __tablename__ = "enriched_user_mv"
    user_id = Column(None, ForeignKey("enriched_user.user_id"), primary_key=True)

    __mapper_args__ = {
        "polymorphic_identity": "mv",
        "inherit_condition": (user_id == User.user_id),
    }


def get_available_table(engine, model_base) -> str:
    for suffix in ["", "Mv", "MvTmp", "MvOld"]:
        model = f"{model_base}{suffix}"
        try:
            table_name = eval(model).__tablename__
            result = inspect(engine).has_table(table_name)
            print(eval(model), result)
        except NameError:
            print(f"Model {model} is not defined")
        if result:
            return eval(model)
        else:
            print(f"{model_base} table does not exist in database.")
            return None
