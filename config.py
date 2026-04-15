import keyring


API_KEY = keyring.get_password("vireo-scope-loop", "vireo-scope-loop")
MODEL_LOW = "claude-sonnet-4-5"
MODEL_HIGH = "claude-opus-4-6"
MAX_TOKENS = 4096

FREQUENCY_THRESHOLD = 3
ROLE_THRESHOLD = 2
WORKFLOWS_PER_CALL = 10
ITERATIONS_PER_ROLE = 5

ROLES = [
    ("FP&A Analyst", 0.40),
    ("FP&A Manager", 0.20),
    ("Treasury Analyst", 0.10),
    ("Credit Analyst", 0.10),
    ("Project Finance Analyst", 0.10),
    ("Corporate Development Associate", 0.05),
    ("Controller", 0.05),
]