import requests

class QueryHandler:
    def __init__(self, config, retriever):
        self.config = config
        self.retriever = retriever

    def build_context(self, query, k=5, project=None, max_context_length=3000):
        """
        Build a context string from retrieved code chunks, with clear delimiters and context length management.
        """
        chunks_by_project = self.retriever.retrieve_chunks(query, k, project)
        context_chunks = []
        total_length = 0
        for proj, chunks in chunks_by_project.items():
            for chunk in chunks:
                chunk_text = (
                    f"-----\n# Project: {proj}\n# File: {chunk['file_path']} [{chunk['start_line']}:{chunk['end_line']}]\n"
                    f"{chunk['code']}\n-----\n"
                )
                chunk_len = len(chunk_text)
                if total_length + chunk_len > max_context_length:
                    break
                context_chunks.append(chunk_text)
                total_length += chunk_len
        return "\n".join(context_chunks)

    def ask(self, query, k=5, project=None):
        context = self.build_context(query, k, project)
        prompt = (
            "You are a codebase assistant. Use ONLY the provided code context to answer the question. "
            "If the answer is not present, reply: 'Not found in context.'\n\n"
            "Relevant code context from the selected project(s):\n\n"
            f"{context}\n\n"
            f"Question: {query}\n"
            f"Answer:"
        )
        print(f"Sending prompt to Ollama: {prompt}")
        url = f"{self.config['ollama_base_url']}/api/generate"
        payload = {
            "model": self.config['models']['qna_model'],
            "prompt": prompt,
            "stream": False,
        }
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        print(f"Received response from Ollama: {resp.json()['response']}")
        return resp.json()['response']

