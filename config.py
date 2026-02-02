"""System configurations for the Rolodex interview intelligence system."""

from enum import Enum
from pathlib import Path


class PersonType(str, Enum):
    """Types of people tracked in the system."""
    CUSTOMER = "customer"
    INVESTOR = "investor"
    COMPETITOR = "competitor"


class Tag(str, Enum):
    """Thematic tags for categorizing interview insights."""
    PRICING = "pricing"
    PRODUCT = "product"
    GTM = "gtm"
    COMPETITORS = "competitors"
    MARKET = "market"


TAG_DESCRIPTIONS = {
    Tag.PRICING: "Pricing models, willingness to pay, cost concerns",
    Tag.PRODUCT: "Features, UX, functionality, bugs, requests",
    Tag.GTM: "Go-to-market strategy, sales, distribution, channels",
    Tag.COMPETITORS: "Competitive landscape, alternatives, switching",
    Tag.MARKET: "Industry trends, market size, timing, macro factors",
}

# Model settings
MODEL_NAME = "gemini-2.5-flash"
MODEL_TEMPERATURE = 0.3
SPEAKER_ID_MAX_TOKENS = 1024
ANALYSIS_MAX_TOKENS = 16384
ROLLING_UPDATE_MAX_TOKENS = 4096

# Database settings
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "rolodex.db"

# Audio extraction settings
AUDIO_FORMAT = "wav"
AUDIO_SAMPLE_RATE = 16000
