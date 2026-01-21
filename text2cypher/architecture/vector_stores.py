import os
from langchain_core.embeddings import Embeddings
from langchain_neo4j import Neo4jGraph
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy

# from gensim.models.fasttext import load_facebook_model
import compress_fasttext
from model2vec import StaticModel
from langchain_core.embeddings import Embeddings

from typing import List

class FastTextEmbeddings(Embeddings):
    
    def __init__(self, model_path: str):
        # self.model = model = load_facebook_model("./models/fasttext/cc.en.300.compressed.bin")
        self.model = compress_fasttext.models.CompressedFastTextKeyedVectors.load(
            model_path
        )
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.model.get_vector(text) for text in texts]
    
    def embed_query(self, text: str) -> List[float]:
        text = text.replace("_", " ").lower()
        return self.model.get_vector(text)

class Model2VecEmbeddings(Embeddings):
    """
    Model2Vec embeddings using static embeddings distilled from transformer models.
    Model2Vec is state-of-the-art for static embeddings, offering high quality
    embeddings with efficient inference.
    """
    
    def __init__(self, model_path: str):
        """
        Initialize Model2Vec embeddings.
        
        Args:
            model_path: Path to the model2vec model file or HuggingFace model name
                       (e.g., "minishlab/M2V_base_output")
        """
        self.model = StaticModel.from_pretrained(model_path)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        embeddings = self.model.encode(texts)
        return embeddings.tolist()
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        text = text.replace("_", " ").lower()
        embedding = self.model.encode([text])
        return embedding[0].tolist()


class FAISSIndex:

    __slots__ = (
        "node_index",
        "rel_index",
        "prop_index",
        "neo4j",
        "embedding_model",
        "indexes_dir",
        "retrieval_config",
    )

    def __init__(
        self,
        neo4j: Neo4jGraph,
        embedding_model: Embeddings,
        indexes_dir: str,
    ):
        self.neo4j = neo4j
        self.embedding_model = embedding_model
        self.indexes_dir = indexes_dir
        self.retrieval_config = {
            # here we use euclidean distance (norm L2) with L2 normalization
            # to normalize embeddings to unit length
            "distance_strategy": DistanceStrategy.EUCLIDEAN_DISTANCE,
            "normalize_L2": True,  # FAISS normalizes all embeddings to unit length
            # since embeddings are normalized to unit length, then 
            # l2_norm = ||u - v||² = ||u||² + ||v||² - 2(u · v)
            # = 1 + 1 - 2(u · v)
            # = 2(1 - u · v) = 2(1 - cos(θ))
            # we can use the following function to convert L2 distance to cosine similarity
            "relevance_score_fn": lambda l2_norm: 1.0 - l2_norm / 2.0, # cos(θ) = 1 - d²/2 in [-1, 1]
            # if we want cosine similarity to be normalized between 0 and 1
            # then relevance_score_fn should be:
            "relevance_score_fn": lambda l2_norm: ((1.0 - l2_norm / 4.0) + 1) / 2.0, # in [0, 1]
        }

        if os.path.exists(self.indexes_dir):
            self.load_indexes()
        else:
            self.create_indexes()

    def load_indexes(self) -> None:
        self.node_index = FAISS.load_local(
            folder_path=f"{self.indexes_dir}/node_index",
            allow_dangerous_deserialization=True,
            embeddings=self.embedding_model,
            **self.retrieval_config
        )
        self.rel_index = FAISS.load_local(
            folder_path=f"{self.indexes_dir}/rel_index",
            allow_dangerous_deserialization=True,
            embeddings=self.embedding_model,
            **self.retrieval_config
        )
        self.prop_index = FAISS.load_local(
            folder_path=f"{self.indexes_dir}/prop_index",
            allow_dangerous_deserialization=True,
            embeddings=self.embedding_model,
            **self.retrieval_config
        )

    def save_indexes(self) -> None:
        self.node_index.save_local(
            folder_path=f"{self.indexes_dir}/node_index"
        )
        self.rel_index.save_local(
            folder_path=f"{self.indexes_dir}/rel_index"
        )
        self.prop_index.save_local(
            folder_path=f"{self.indexes_dir}/prop_index"
        )

    def create_indexes(self) -> None:
        query = "CALL db.labels() YIELD label RETURN label"
        labels = [record['label'] for record in self.neo4j.query(query)]
        self.node_index = FAISS.from_texts(
            texts=labels,
            embedding=self.embedding_model,
            **self.retrieval_config
        )

        query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        rel_types = [record['relationshipType'] for record in self.neo4j.query(query)]
        self.rel_index = FAISS.from_texts(
            texts=rel_types,
            embedding=self.embedding_model,
            **self.retrieval_config
        )

        query = "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey"
        prop_keys = [record['propertyKey'] for record in self.neo4j.query(query)]
        self.prop_index = FAISS.from_texts(
            texts=prop_keys,
            embedding=self.embedding_model,
            **self.retrieval_config
        )

        self.save_indexes()

if __name__ == "__main__":
    # model = FastTextEmbeddings("./models/fasttext/cc.en.300.compressed.bin")
    # # Get first 3 keys
    # # first_3_keys = list(model.model.key_to_index.keys())
    # # print(first_3_keys)
    # # get embedding for "peptide"
    # print(model.model.get_vector("hasceo"))

    model = Model2VecEmbeddings("minishlab/M2V_base_output")
    embedding = model.embed_query("peptide")
    print(embedding)