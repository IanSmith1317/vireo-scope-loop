import keyring


API_KEY = keyring.get_password("vireo-scope-loop","vireo-scope-loop")
MODEL_LOW = "claude-sonnet-4-5"
MODEL_HIGH = "claude-opus-4-6"
MAX_TOKENS = 4096