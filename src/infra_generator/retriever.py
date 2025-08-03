import requests


class Retriever:
    def __init__(self, config: dict, chroma_manager):
        self.config = config
        self.chroma_manager = chroma_manager

    def embed_query(self, query: str):
        url = f"{self.config['ollama_base_url']}/api/embeddings"
        payload = {"model": self.config["models"]["embed_model"], "prompt": query}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()["embedding"]

    def retrieve_chunks(self, query, k=5, project=None):
        results = {}
        projects = [project] if project else self.chroma_manager.get_all_projects()
        if not projects:
            print("No embedded projects found.")
            return results
        for proj in projects:
            collection = self.chroma_manager.get_collection(proj)
            vector = self.embed_query(query)
            res = collection.query(query_embeddings=[vector], n_results=k)
            hits = []
            for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
                hits.append(
                    {
                        "code": doc,
                        "file_path": meta["file_path"],
                        "start_line": meta.get("start_line", -1),
                        "end_line": meta.get("end_line", -1),
                        "language": meta["language"],
                        "project": meta.get("project", proj),
                    }
                )
            results[proj] = hits
        return results
