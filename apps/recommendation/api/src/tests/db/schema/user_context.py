from tests.db.schema.user import (
    user_profile_unknown,
    user_profile_null,
    user_profile_111,
    user_profile_118,
    user_profile_117,
)
from tests.db.schema.iris import (
    iris_paris_chatelet,
    iris_unknown,
    iris_nok,
    iris_marseille_cours_julien,
    iris_marseille_vieux_port,
)
from huggy.schemas.user import UserContext

user_context_unknown_paris = UserContext(
    found=False,
    is_geolocated=True,
    **iris_paris_chatelet.dict(),
    **user_profile_unknown.dict()
)
user_context_null_nok = UserContext(
    found=True, is_geolocated=False, **iris_nok.dict(), **user_profile_null.dict()
)
user_context_111_paris = UserContext(
    found=True,
    is_geolocated=True,
    **iris_paris_chatelet.dict(),
    **user_profile_111.dict()
)
user_context_111_unknown = UserContext(
    found=True, is_geolocated=False, **iris_unknown.dict(), **user_profile_111.dict()
)
user_context_118_paris = UserContext(
    found=True,
    is_geolocated=True,
    **iris_paris_chatelet.dict(),
    **user_profile_118.dict()
)
user_context_117_paris = UserContext(
    found=True,
    is_geolocated=True,
    **iris_paris_chatelet.dict(),
    **user_profile_117.dict()
)

user_context_111_vieux_port_marseille = UserContext(
    found=True,
    is_geolocated=True,
    **iris_marseille_vieux_port.dict(),
    **user_profile_111.dict()
)

user_context_111_cours_julien_marseille = UserContext(
    found=True,
    is_geolocated=True,
    **iris_marseille_cours_julien.dict(),
    **user_profile_111.dict()
)
