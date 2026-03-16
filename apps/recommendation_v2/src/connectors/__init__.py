from config import settings
from connectors.vertex_api import VertexAPI


retrieval_api_client = VertexAPI(endpoint_name=settings.VERTEX_RETRIEVAL_ENDPOINT_NAME)
ranking_api_client = VertexAPI(endpoint_name=settings.VERTEX_RANKING_ENDPOINT_NAME)
