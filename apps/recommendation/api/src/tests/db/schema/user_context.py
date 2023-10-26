from huggy.schemas.user import UserContext
from tests.db.schema.iris import (
    iris_marseille_cours_julien,
    iris_marseille_vieux_port,
    iris_nok,
    iris_paris_chatelet,
    iris_unknown,
)
from tests.db.schema.user import (
    user_profile_111,
    user_profile_117,
    user_profile_118,
    user_profile_null,
    user_profile_unknown,
)

user_context_unknown_paris = UserContext(
    found=False,
    is_geolocated=True,
    **iris_paris_chatelet.model_dump(),
    **user_profile_unknown.model_dump()
)
user_context_null_nok = UserContext(
    found=True,
    is_geolocated=False,
    **iris_nok.model_dump(),
    **user_profile_null.model_dump()
)
user_context_111_paris = UserContext(
    found=True,
    is_geolocated=True,
    **iris_paris_chatelet.model_dump(),
    **user_profile_111.model_dump()
)
user_context_111_unknown = UserContext(
    found=True,
    is_geolocated=False,
    **iris_unknown.model_dump(),
    **user_profile_111.model_dump()
)
user_context_118_paris = UserContext(
    found=True,
    is_geolocated=True,
    **iris_paris_chatelet.model_dump(),
    **user_profile_118.model_dump()
)
user_context_117_paris = UserContext(
    found=True,
    is_geolocated=True,
    **iris_paris_chatelet.model_dump(),
    **user_profile_117.model_dump()
)

user_context_111_vieux_port_marseille = UserContext(
    found=True,
    is_geolocated=True,
    **iris_marseille_vieux_port.model_dump(),
    **user_profile_111.model_dump()
)

user_context_111_cours_julien_marseille = UserContext(
    found=True,
    is_geolocated=True,
    **iris_marseille_cours_julien.model_dump(),
    **user_profile_111.model_dump()
)
