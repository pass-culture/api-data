from dataclasses import dataclass
from typing import Union

import mlflow
from main import custom_logger
from pcpapillon.utils.constants import ModelName, ModelType
from pcpapillon.utils.data_model import ComplianceInput, ComplianceOutput
from pcpapillon.utils.model_handler import ModelHandler, ModelWithMetadata
from sentence_transformers import SentenceTransformer


@dataclass
class ModelData:
    classification_model: Union[mlflow.pyfunc.PythonModel, SentenceTransformer]
    model_identifier: str
    preprocessing_models: dict[str, SentenceTransformer]


class ComplianceModel:
    MODEL_NAME = ModelName.COMPLIANCE
    MODEL_TYPE = ModelType.DEFAULT
    PREPROC_MODEL_TYPE = MODEL_TYPE.PREPROCESSING

    def __init__(self):
        self.model_handler = ModelHandler()
        model_data = self._load_models()
        self.model = model_data.model
        self.model_identifier = model_data.model_identifier

    def _load_models(
        self,
    ) -> ModelWithMetadata:
        custom_logger.info(f"load {self.MODEL_NAME} model..")
        return self.model_handler.get_model_with_metadata_by_name(
            model_name=self.MODEL_NAME, model_type=self.MODEL_TYPE
        )

    def predict(self, data: ComplianceInput) -> ComplianceOutput:
        """
        Predicts the class labels for the given data using the trained classifier model.

        Args:
            data (ComplianceInput): Input data to be predicted.

        Returns:
            ComplianceOutput: An object containing the predicted class labels
                and the main contributions.
        """
        predictions = self.model.predict(data.dict())
        return ComplianceOutput(
            offer_id=data.offer_id,
            probability_validated=predictions.probability_validated,
            validation_main_features=predictions.validation_main_features,
            probability_rejected=predictions.probability_rejected,
            rejection_main_features=predictions.rejection_main_features,
        )

    def _is_newer_model_available(self) -> bool:
        return (
            self.classifier_model_identifier
            != self.model_handler.get_model_hash_from_mlflow(self.MODEL_NAME)
        )

    def reload_model_if_newer_is_available(self):
        custom_logger.debug("Checking if newer model is available...")
        if self._is_newer_model_available():
            custom_logger.info("New model available: Loading it...")
            classfier_model_with_metadata = (
                self.model_handler.get_model_with_metadata_by_name(
                    model_name=self.MODEL_NAME, model_type=self.MODEL_TYPE
                )
            )
            self.classfier_model, self.classifier_model_identifier = (
                classfier_model_with_metadata.model,
                classfier_model_with_metadata.model_identifier,
            )
            custom_logger.info(
                f"...New model loaded with hash {self.classifier_model_identifier}"
            )
        else:
            custom_logger.debug("...No newer model available")
