"""Virtual filesystem resolver that maps paths to database content."""

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from database import get_interactions, get_person, list_persons
from models import Interaction, Person


class NodeType(Enum):
    ROOT = "root"
    PERSON_DIR = "person_dir"
    PERSON_FILE = "person_file"
    INTERACTIONS_DIR = "interactions_dir"
    INTERACTION_DIR = "interaction_dir"
    INTERACTION_FILE = "interaction_file"


@dataclass
class VFSNode:
    node_type: NodeType
    path: str
    name: str
    is_dir: bool
    children: list[str] = field(default_factory=list)
    content: str = ""


def _name_to_slug(name: str) -> str:
    """Convert a person name to a path slug (spaces to underscores)."""
    return name.replace(" ", "_")


def _slug_to_name(slug: str) -> str:
    """Convert a path slug back to a person name (underscores to spaces)."""
    return slug.replace("_", " ")


def _build_date_slugs(interactions: list[Interaction]) -> dict[str, Interaction]:
    """Group interactions by date, producing slug->Interaction mapping.

    First interaction on a date gets a bare date slug (2026-01-05),
    subsequent ones get _2, _3, etc., ordered by internal DB id.
    """
    by_date: dict[str, list[Interaction]] = defaultdict(list)
    for interaction in interactions:
        date_str = interaction.date.strftime("%Y-%m-%d")
        by_date[date_str].append(interaction)

    slug_map: dict[str, Interaction] = {}
    for date_str, group in by_date.items():
        group.sort(key=lambda i: i.id)
        if len(group) == 1:
            slug_map[date_str] = group[0]
        else:
            for idx, interaction in enumerate(group, start=1):
                slug_map[f"{date_str}_{idx}"] = interaction
    return slug_map


def _format_transcript(interaction: Interaction) -> str:
    """Format a transcript for display."""
    utterances = interaction.transcript.get("utterances", [])
    if utterances:
        lines = []
        for u in utterances:
            lines.append(f"{u['speaker']}: {u['text']}")
        return "\n".join(lines)
    text = interaction.transcript.get("text", "")
    return text if text else "(no transcript available)"


def _format_takeaways(interaction: Interaction) -> str:
    """Format takeaways for display."""
    if not interaction.takeaways:
        return "(no takeaways)"
    return "\n".join(f"- {t}" for t in interaction.takeaways)


def _format_tags(interaction: Interaction) -> str:
    """Format tags for display."""
    if not interaction.tags:
        return "(no tags)"
    return "\n".join(t.value for t in interaction.tags)


def _format_info(person: Person) -> str:
    """Format person info file."""
    lines = [
        f"Name:         {person.name}",
        f"Company:      {person.current_company}",
        f"Type:         {person.type.value}",
        f"Interactions: {len(person.interaction_ids)}",
    ]
    return "\n".join(lines)


PERSON_FILES = ["info", "background", "state", "delta"]
INTERACTION_FILES = ["transcript", "takeaways", "tags"]


def resolve(path: str) -> Optional[VFSNode]:
    """Parse a virtual path and return the corresponding VFSNode."""
    # Normalize path
    path = path.rstrip("/") or "/"
    parts = [p for p in path.split("/") if p]

    # Root
    if not parts:
        persons = list_persons()
        children = sorted(_name_to_slug(p.name) + "/" for p in persons)
        return VFSNode(
            node_type=NodeType.ROOT,
            path="/",
            name="/",
            is_dir=True,
            children=children,
        )

    # First segment is always a person slug
    person_slug = parts[0]
    person_name = _slug_to_name(person_slug)
    person = get_person(person_name)
    if person is None:
        return None

    # /Person/
    if len(parts) == 1:
        children = PERSON_FILES.copy()
        children.append("interactions/")
        return VFSNode(
            node_type=NodeType.PERSON_DIR,
            path=f"/{person_slug}",
            name=person_slug,
            is_dir=True,
            children=children,
        )

    # /Person/<file>
    if len(parts) == 2 and parts[1] in PERSON_FILES:
        file_name = parts[1]
        content_map = {
            "info": lambda: _format_info(person),
            "background": lambda: person.background or "(no background)",
            "state": lambda: person.state_of_play or "(no state of play)",
            "delta": lambda: person.last_delta or "(no delta)",
        }
        return VFSNode(
            node_type=NodeType.PERSON_FILE,
            path=f"/{person_slug}/{file_name}",
            name=file_name,
            is_dir=False,
            content=content_map[file_name](),
        )

    # /Person/interactions...
    if parts[1] != "interactions":
        return None

    interactions = get_interactions(person_name)
    slug_map = _build_date_slugs(interactions)

    # /Person/interactions/
    if len(parts) == 2:
        children = sorted(s + "/" for s in slug_map.keys())
        return VFSNode(
            node_type=NodeType.INTERACTIONS_DIR,
            path=f"/{person_slug}/interactions",
            name="interactions",
            is_dir=True,
            children=children,
        )

    # /Person/interactions/<date_slug>
    date_slug = parts[2]
    if date_slug not in slug_map:
        return None
    interaction = slug_map[date_slug]

    if len(parts) == 3:
        return VFSNode(
            node_type=NodeType.INTERACTION_DIR,
            path=f"/{person_slug}/interactions/{date_slug}",
            name=date_slug,
            is_dir=True,
            children=INTERACTION_FILES.copy(),
        )

    # /Person/interactions/<date_slug>/<file>
    if len(parts) == 4 and parts[3] in INTERACTION_FILES:
        file_name = parts[3]
        content_map = {
            "transcript": lambda: _format_transcript(interaction),
            "takeaways": lambda: _format_takeaways(interaction),
            "tags": lambda: _format_tags(interaction),
        }
        return VFSNode(
            node_type=NodeType.INTERACTION_FILE,
            path=f"/{person_slug}/interactions/{date_slug}/{file_name}",
            name=file_name,
            is_dir=False,
            content=content_map[file_name](),
        )

    return None


def resolve_path(cwd: str, user_path: str) -> str:
    """Resolve a potentially relative path against a cwd.

    Handles '.', '..', absolute paths, and relative paths.
    Returns an absolute virtual path.
    """
    if user_path.startswith("/"):
        working = user_path
    else:
        working = cwd.rstrip("/") + "/" + user_path

    parts = working.split("/")
    resolved: list[str] = []
    for part in parts:
        if part == "" or part == ".":
            continue
        elif part == "..":
            if resolved:
                resolved.pop()
        else:
            resolved.append(part)

    return "/" + "/".join(resolved)


def tree(path: str, prefix: str = "", max_depth: int = 4) -> str:
    """Generate a tree view starting from the given path."""
    node = resolve(path)
    if node is None:
        return f"Path not found: {path}"

    lines: list[str] = []
    _tree_recursive(path, node, lines, prefix="", depth=0, max_depth=max_depth)
    return "\n".join(lines)


def _tree_recursive(
    path: str,
    node: VFSNode,
    lines: list[str],
    prefix: str,
    depth: int,
    max_depth: int,
) -> None:
    """Recursively build tree lines."""
    if depth > max_depth:
        return

    if depth == 0:
        lines.append(node.name if node.name != "/" else ".")

    if not node.is_dir:
        return

    children = node.children
    for i, child_name in enumerate(children):
        is_last = i == len(children) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{child_name}")

        if child_name.endswith("/"):
            child_path = path.rstrip("/") + "/" + child_name.rstrip("/")
            child_node = resolve(child_path)
            if child_node is not None:
                extension = "    " if is_last else "│   "
                _tree_recursive(
                    child_path, child_node, lines,
                    prefix=prefix + extension,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
