from pydantic_settings import BaseSettings


class LLMSettings(BaseSettings):
    # API configuration
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000

    # Embedding configuration
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1024

    # Batch processing
    llm_batch_size: int = 10
    llm_rate_limit_rpm: int = 60

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


llm_settings = LLMSettings()
