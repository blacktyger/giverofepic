SUCCESS = False
ERROR = True

DELETE_AFTER_MINUTES = 15
TIME_LOCK_MINUTES = 2
ATTEMPTS_INTERVAL = 3
NUM_OF_ATTEMPTS = 3

MINIMUM_CONFIRMATIONS = 2
TRANSACTION_ARGS = ('address', 'amount', 'event', 'code')
DEFAULT_FEE = 0.008
MAX_AMOUNT = 5

GIVEAWAY_LINKS_SHORT_WORKSPACE = "e9b41228264a4f5e94089e83c73c2b76"
GIVEAWAY_LINKS_SHORT_DOMAIN_ID = "d983e29e62e94729b2456c278976e33f"
GIVEAWAY_LINKS_LIFETIME_MINUTES = 60 * 24

# QUIZ_MIN_POINT_FOR_REWARD = 5
# QUIZ_LINKS_LIFETIME_MINUTES = 60 * 24
# QUIZ_USER_TIME_LOCK_MINUTES = 60 * 24 * 7

LOCAL_WALLET_API_URL = 'localhost:8000/api/wallet'

API_KEY_HEADER = "X-API-Key"
DEFAULT_SECRET_KEY = 'default_secret_key'

EPICBOX_DOMAIN = 'epicbox.epic.tech'
EPICBOX_PORT = 0

SECRETS_PATH_PREFIX = 'Wallets/'
VALID_EVENT_NAMES = ['giveaway', 'faucet', 'equinox', 'test', 'fakeologist']
WALLETS = ['faucet_1', 'faucet_2']