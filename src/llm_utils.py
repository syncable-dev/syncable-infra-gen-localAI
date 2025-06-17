# llm_utils.py

from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from typing import Any


def call_llm(
    prompt: str,
    base_url: str,
    model: str,
    temperature: float = 0.0
) -> str:
    """
    Invoke Ollama and return the LLM's response content.
    """
    llm = ChatOllama(base_url=base_url, model=model, temperature=temperature)
    prompt_template = ChatPromptTemplate.from_template("{input}")
    chain = prompt_template | llm
    response = chain.invoke({"input": prompt})
    return response.content
