import mlflow
import mlflow.pyfunc
from catboost import CatBoostClassifier
from pcpapillon.utils.env_vars import ENV_SHORT_NAME, MLFLOW_CLIENT_ID
from pcpapillon.utils.tools import connect_remote_mlflow
from sentence_transformers import SentenceTransformer


class ModelHandler:
    @staticmethod
    def get_model_by_name(name, type="default"):
        if name == "compliance":
            if type == "local":
                model = CatBoostClassifier(one_hot_max_size=65)
                model_loaded = model.load_model("./pcpapillon/local_model/model.cb")
            else:
                connect_remote_mlflow(MLFLOW_CLIENT_ID)
                model_loaded = mlflow.catboost.load_model(
                    model_uri=f"models:/{name}_{type}_{ENV_SHORT_NAME}/Production"
                )
            return model_loaded
        elif name == "offer_categorisation":
            if type == "local":
                model = CatBoostClassifier(one_hot_max_size=65)
                model_loaded = model.load_model(
                    "./pcpapillon/local_model/offer_categorisation_model.cb"
                )
            else:
                connect_remote_mlflow(MLFLOW_CLIENT_ID)
                model_loaded = mlflow.catboost.load_model(
                    model_uri=f"models:/{name}_{type}_{ENV_SHORT_NAME}/Production"
                )
            return model_loaded
        else:
            if type == "custom_sentence_transformer":
                return SentenceTransformer(name)
            raise ValueError(
                f"Model {name} with type {type} not found. name should be one of ['compliance', 'offer_categorisation']"
                " if type is not 'custom_sentence_transformer' and a valid SentenceTransformer model name, if type is 'custom_sentence_transformer'"
            )
