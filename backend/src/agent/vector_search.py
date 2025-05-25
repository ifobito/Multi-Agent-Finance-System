import os
from typing import Dict
from elasticsearch import Elasticsearch
from langchain_openai import OpenAIEmbeddings
from langchain_elasticsearch import ElasticsearchRetriever

es_url = "http://localhost:9200"
index_name = "test-langchain-retriever"
text_field = "text"
dense_vector_field = "embedding"
api_key = os.getenv("OPENAI_API_KEY") 

es_client = Elasticsearch(hosts=[es_url])

embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=api_key)

def hybrid_query(search_query: str) -> Dict:
    """Define a hybrid query combining BM25 and vector search without RRF."""
    vector = embeddings.embed_query(search_query)
    return {
        "query": {
            "bool": {
                "should": [
                    {
                        "match": {
                            text_field: {
                                "query": search_query,
                                "boost": 1.0  
                            }
                        }
                    },
                    {
                        "script_score": {
                            "query": {"match_all": {}},
                            "script": {
                                "source": f"cosineSimilarity(params.query_vector, '{dense_vector_field}') + 1.0",
                                "params": {"query_vector": vector}
                            },
                            "boost": 1.0  
                        }
                    }
                ],
                "minimum_should_match": 1
            }
        }
    }

def main():
    try:
        hybrid_retriever = ElasticsearchRetriever.from_es_params(
            index_name=index_name,
            body_func=hybrid_query,
            content_field=text_field,
            url=es_url,
        )
        
        query = "Trong bộ dữ liệu TAG, trường nào xác định xem một thẻ (tag) là chuẩn hay tùy chỉnh?"
        results = hybrid_retriever.invoke(query)
        
        print(f"Hybrid search results for query '{query}':")
        for i, doc in enumerate(results, 1):
            # print(f"{i}. {doc.page_content} (Metadata: {doc.metadata})")
            print(doc.metadata)
    
    except Exception as e:
        print(f"Error performing hybrid search: {e}")

if __name__ == "__main__":
    main()