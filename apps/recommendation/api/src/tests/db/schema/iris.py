from pydantic import BaseModel

import typing as t


class IrisTestExample(BaseModel):
    longitude: t.Optional[float]
    latitude: t.Optional[float]
    iris_id: t.Optional[str]


iris_paris_chatelet = IrisTestExample(
    longitude=2.33294778256192, latitude=48.831930605740254, iris_id="45327"
)  # default centroid (Paris)
iris_nok = IrisTestExample(longitude=None, latitude=None, iris_id=None)  # none
iris_unknown = IrisTestExample(
    longitude=-122.1639346, latitude=37.4449422, iris_id=None
)  # unknown

iris_marseille_vieux_port = IrisTestExample(
    longitude=5.36985889447414, latitude=43.2963673603911, iris_id="22971"
)  # default centroid (Marseille, old port)


iris_marseille_cours_julien = IrisTestExample(
    longitude=5.38402043954079, latitude=43.2937465050196, iris_id="25195"
)  # default centroid (Marseille, cours Julien)
