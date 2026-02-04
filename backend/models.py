"""Data classes for the Rolodex interview intelligence system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config import PersonType, Tag


@dataclass
class Person:
    """A person tracked in the Rolodex system."""
    name: str                              # Primary key
    current_company: str                   # Where they work now
    type: PersonType                       # Customer/Investor/Competitor
    background: str = ""                   # Static bio
    linkedin_url: str = ""                 # LinkedIn profile URL (optional)
    company_industry: str = ""             # Industry of their company (optional)
    company_size: str = ""                 # Company size (optional)
    state_of_play: str = ""                # AI-updated current truth (~200 words)
    last_delta: str = ""                   # What changed in most recent meeting
    interaction_ids: list[int] = field(default_factory=list)  # IDs of linked interactions

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "name": self.name,
            "current_company": self.current_company,
            "type": self.type.value,
            "background": self.background,
            "linkedin_url": self.linkedin_url,
            "company_industry": self.company_industry,
            "company_size": self.company_size,
            "state_of_play": self.state_of_play,
            "last_delta": self.last_delta,
        }

    @classmethod
    def from_dict(cls, data: dict, interaction_ids: list[int] = None) -> "Person":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            current_company=data["current_company"],
            type=PersonType(data["type"]),
            background=data.get("background", ""),
            linkedin_url=data.get("linkedin_url", ""),
            company_industry=data.get("company_industry", ""),
            company_size=data.get("company_size", ""),
            state_of_play=data.get("state_of_play", ""),
            last_delta=data.get("last_delta", ""),
            interaction_ids=interaction_ids or [],
        )


@dataclass
class Interaction:
    """A recorded interaction with a person."""
    id: Optional[int]                      # Auto-generated primary key
    person_name: str                       # Foreign key to Person
    date: datetime                         # When the interaction occurred
    transcript: dict                       # Speaker-tagged JSON
    takeaways: list[str] = field(default_factory=list)  # Key insights
    tags: list[Tag] = field(default_factory=list)       # Thematic tags

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "person_name": self.person_name,
            "date": self.date.isoformat(),
            "transcript": self.transcript,
            "takeaways": self.takeaways,
            "tags": [t.value for t in self.tags],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Interaction":
        """Create from dictionary."""
        return cls(
            id=data.get("id"),
            person_name=data["person_name"],
            date=datetime.fromisoformat(data["date"]),
            transcript=data["transcript"],
            takeaways=data.get("takeaways", []),
            tags=[Tag(t) for t in data.get("tags", [])],
        )


@dataclass
class InteractionAnalysis:
    """Result of analyzing an interaction transcript."""
    takeaways: list[str]
    tags: list[Tag]


@dataclass
class RollingUpdate:
    """Result of generating a rolling update for a person."""
    delta: str           # What changed (1-2 sentences)
    updated_state: str   # New state_of_play (~200 words)
