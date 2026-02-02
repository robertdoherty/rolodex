"""CLI entry point for the Rolodex interview intelligence system."""

from datetime import datetime

import click

import vfs
from config import PersonType, Tag, TAG_DESCRIPTIONS
from database import (
    create_person,
    get_interactions,
    get_interactions_by_tag,
    get_person,
    init_db,
    list_persons,
)
from services.ingestion import ingest_recording


@click.group()
def cli():
    """Rolodex - Interview Intelligence System"""
    init_db()


@cli.group()
def person():
    """Manage people in the Rolodex."""
    pass


@person.command("create")
@click.argument("name")
@click.option("--company", "-c", required=True, help="Current company")
@click.option(
    "--type", "-t",
    "person_type",
    required=True,
    type=click.Choice(["customer", "investor", "competitor"]),
    help="Person type",
)
@click.option("--background", "-b", default="", help="Background/bio")
def person_create(name: str, company: str, person_type: str, background: str):
    """Create a new person in the Rolodex."""
    ptype = PersonType(person_type)
    p = create_person(name, company, ptype, background)
    click.echo(f"Created {p.type.value}: {p.name} @ {p.current_company}")


@person.command("show")
@click.argument("name")
def person_show(name: str):
    """Show details for a person."""
    p = get_person(name)
    if p is None:
        click.echo(f"Person '{name}' not found.")
        return

    click.echo(f"\n{'='*60}")
    click.echo(f"Name: {p.name}")
    click.echo(f"Company: {p.current_company}")
    click.echo(f"Type: {p.type.value}")
    click.echo(f"Interactions: {len(p.interaction_ids)}")
    click.echo(f"{'='*60}")

    if p.background:
        click.echo(f"\nBackground:\n{p.background}")

    if p.last_delta:
        click.echo(f"\nLast Delta:\n{p.last_delta}")

    if p.state_of_play:
        click.echo(f"\nState of Play:\n{p.state_of_play}")

    click.echo()


@person.command("list")
@click.option(
    "--type", "-t",
    "person_type",
    type=click.Choice(["customer", "investor", "competitor"]),
    help="Filter by type",
)
def person_list(person_type: str | None):
    """List all people in the Rolodex."""
    ptype = PersonType(person_type) if person_type else None
    persons = list_persons(ptype)

    if not persons:
        click.echo("No people found.")
        return

    click.echo(f"\n{'Name':<25} {'Company':<25} {'Type':<12} {'Interactions'}")
    click.echo("-" * 75)
    for p in persons:
        click.echo(f"{p.name:<25} {p.current_company:<25} {p.type.value:<12} {len(p.interaction_ids)}")
    click.echo()


@cli.command()
@click.argument("video_path", type=click.Path(exists=True))
@click.option("--person", "-p", "person_name", required=True, help="Person name")
@click.option("--date", "-d", default=None, help="Date (YYYY-MM-DD), defaults to today")
def ingest(video_path: str, person_name: str, date: str | None):
    """Ingest a recording and process through the pipeline."""
    interaction_date = None
    if date:
        interaction_date = datetime.strptime(date, "%Y-%m-%d")

    try:
        interaction = ingest_recording(video_path, person_name, interaction_date)
        click.echo(f"\nTakeaways:")
        for t in interaction.takeaways:
            click.echo(f"  - {t}")
        click.echo(f"\nTags: {', '.join(t.value for t in interaction.tags)}")
    except ValueError as e:
        click.echo(f"Error: {e}")
    except FileNotFoundError as e:
        click.echo(f"Error: {e}")


@cli.group()
def search():
    """Search interactions."""
    pass


@search.command("tag")
@click.argument("tag_name", type=click.Choice(["pricing", "product", "gtm", "competitors", "market"]))
def search_tag(tag_name: str):
    """Search interactions by tag."""
    tag = Tag(tag_name)
    interactions = get_interactions_by_tag(tag)

    if not interactions:
        click.echo(f"No interactions found with tag '{tag_name}'.")
        return

    click.echo(f"\nInteractions tagged '{tag_name}' ({TAG_DESCRIPTIONS[tag]}):\n")
    for i in interactions:
        click.echo(f"[{i.date.strftime('%Y-%m-%d')}] {i.person_name}")
        for t in i.takeaways:
            click.echo(f"  - {t}")
        click.echo()


@search.command("person")
@click.argument("name")
def search_person(name: str):
    """Show all interactions for a person."""
    p = get_person(name)
    if p is None:
        click.echo(f"Person '{name}' not found.")
        return

    interactions = get_interactions(name)
    if not interactions:
        click.echo(f"No interactions found for '{name}'.")
        return

    click.echo(f"\nInteractions with {name}:\n")
    for i in interactions:
        tags_str = ", ".join(t.value for t in i.tags)
        click.echo(f"[{i.date.strftime('%Y-%m-%d')}] Tags: {tags_str}")
        for t in i.takeaways:
            click.echo(f"  - {t}")
        click.echo()


@cli.command()
@click.argument("name")
@click.option("--id", "-i", "interaction_id", type=int, default=None, help="Specific interaction ID")
def transcript(name: str, interaction_id: int | None):
    """View the transcript for a person's interaction."""
    p = get_person(name)
    if p is None:
        click.echo(f"Person '{name}' not found.")
        return

    interactions = get_interactions(name)
    if not interactions:
        click.echo(f"No interactions found for '{name}'.")
        return

    if interaction_id is not None:
        interactions = [i for i in interactions if i.id == interaction_id]
        if not interactions:
            click.echo(f"Interaction {interaction_id} not found for '{name}'.")
            return

    for interaction in interactions:
        tags_str = ", ".join(t.value for t in interaction.tags)
        click.echo(f"\n{'='*60}")
        click.echo(f"Interaction #{interaction.id} — {interaction.date.strftime('%Y-%m-%d')} — Tags: {tags_str}")
        click.echo(f"{'='*60}\n")

        utterances = interaction.transcript.get("utterances", [])
        if utterances:
            for u in utterances:
                click.echo(f"  {u['speaker']}: {u['text']}")
        else:
            text = interaction.transcript.get("text", "")
            if text:
                click.echo(text)
            else:
                click.echo("  (no transcript available)")
        click.echo()


@cli.command()
def tags():
    """List all available tags with descriptions."""
    click.echo("\nAvailable Tags:\n")
    for tag in Tag:
        click.echo(f"  {tag.value:<12} - {TAG_DESCRIPTIONS[tag]}")
    click.echo()


@cli.command("shell")
def shell_cmd():
    """Start the interactive Rolodex shell."""
    from shell import RolodexShell
    RolodexShell().run()


@cli.command("ls")
@click.argument("path", default="/")
def ls_cmd(path: str):
    """List virtual filesystem contents."""
    node = vfs.resolve(path)
    if node is None:
        click.echo(f"ls: cannot access '{path}': No such file or directory")
        return
    if not node.is_dir:
        click.echo(node.name)
        return
    for child in node.children:
        click.echo(child)


@cli.command("cat")
@click.argument("path")
def cat_cmd(path: str):
    """Show virtual filesystem file contents."""
    node = vfs.resolve(path)
    if node is None:
        click.echo(f"cat: {path}: No such file or directory")
        return
    if node.is_dir:
        click.echo(f"cat: {path}: Is a directory")
        return
    click.echo(node.content)


if __name__ == "__main__":
    cli()
