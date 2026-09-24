from config import settings
from connectors.vertex_api import VertexAPI


retrieval_api_client = VertexAPI(endpoint_name=settings.VERTEX_RETRIEVAL_ENDPOINT_NAME)
graph_api_client = VertexAPI(endpoint_name=settings.VERTEX_GRAPH_ENDPOINT_NAME)
ranking_api_client = VertexAPI(endpoint_name=settings.VERTEX_RANKING_ENDPOINT_NAME)
# AB TEST — semantic item-to-item retrieval endpoint (RFF), see docs/ab_testing.md
semantic_retrieval_api_client = VertexAPI(endpoint_name=settings.VERTEX_SEMANTIC_ENDPOINT_NAME)
