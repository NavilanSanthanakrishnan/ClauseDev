import os
import logging
from functools import lru_cache
from transformers import AutoTokenizer
from app.core.config import HF_TOKEN, DEFAULT_TOKENIZER

logging.getLogger("transformers").setLevel(logging.ERROR)
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'

@lru_cache(maxsize=4)
def _get_tokenizer(tokenizer_name: str):
    tokenizer = AutoTokenizer.from_pretrained(
        pretrained_model_name_or_path=tokenizer_name,
        token=HF_TOKEN
    )
    tokenizer.model_max_length = 1_000_000
    return tokenizer

def count_tokens(text: str, tokenizer_name: str = DEFAULT_TOKENIZER) -> int:
    tokenizer = _get_tokenizer(tokenizer_name)
    tokens = tokenizer(text)["input_ids"]
    return len(tokens)

def truncate_text(text: str, max_tokens: int, tokenizer_name: str = DEFAULT_TOKENIZER) -> str:
    tokenizer = _get_tokenizer(tokenizer_name)
    tokens = tokenizer(text)["input_ids"]

    if len(tokens) > max_tokens:
        truncated_text = tokenizer.decode(
            tokens[:max_tokens],
            clean_up_tokenization_spaces=True
        )
        return truncated_text

    return text
