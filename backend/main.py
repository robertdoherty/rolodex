"""CLI entry point for the Rolodex interview intelligence system."""

from datetime import datetime

import click

import vfs
from config import PersonType, Tag, TAG_DESCRIPTIONS
from database import (
    add_connection,
    aggregate_segments,
    aggregate_tags,
    complete_followup,
    create_followups,
    create_person,
    delete_interaction,
    delete_person,
    get_interactions,
    get_interactions_by_tag,
    get_open_followups,
    get_person,
    init_db,
    list_persons,
    remove_connection,
    search_interactions,
    search_persons,
    search_text,
)
from services.ingestion import ingest_recording, ingest_transcript


@click.group()
def cli():
    """Rolodex - Interview Intelligence System"""
    init_db()


@cli.group()
def person():
    """Manage people in the Rolodex."""
    pass


@person.command("create")
@click.argument("name", required=False)
@click.option("--company", "-c", default=None, help="Current company")
@click.option(
    "--type", "-t",
    "person_type",
    default=None,
    type=click.Choice(["customer", "investor", "competitor"]),
    help="Person type (optional)",
)
@click.option("--background", "-b", default="", help="Background/bio")
@click.option("--linkedin", "-l", default="", help="LinkedIn profile URL")
@click.option("--industry", "-i", default="", help="Company industry")
@click.option("--revenue", "-r", default="", help="Company revenue ($)")
@click.option("--headcount", "-h", default="", help="Company headcount (people)")
def person_create(name: str | None, company: str | None, person_type: str | None, background: str, linkedin: str, industry: str, revenue: str, headcount: str):
    """Create a new person in the Rolodex.

    Only name and company are required. All other fields are optional.
    """
    # Prompt for missing required fields
    if name is None:
        name = click.prompt("Name")
    if company is None:
        company = click.prompt("Company")

    # Prompt for optional fields if not provided via flags
    if not person_type:
        person_type = click.prompt(
            "Type (customer/investor/competitor)",
            default="",
            show_default=False,
        )
    if not background:
        background = click.prompt("Background", default="", show_default=False)
    if not linkedin:
        linkedin = click.prompt("LinkedIn URL", default="", show_default=False)
    if not industry:
        industry = click.prompt("Industry", default="", show_default=False)
    if not revenue:
        revenue = click.prompt("Revenue ($)", default="", show_default=False)
    if not headcount:
        headcount = click.prompt("Headcount", default="", show_default=False)

    # Connection prompting
    connections = []
    persons = list_persons()
    existing_names = [p.name for p in persons]
    if existing_names:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.completion import FuzzyWordCompleter
        completer = FuzzyWordCompleter(existing_names)
        while True:
            conn_name = pt_prompt("Connection (empty to finish): ", completer=completer).strip()
            if not conn_name:
                break
            if conn_name == name:
                click.echo("  Skipped: cannot connect a person to themselves")
                continue
            if conn_name not in existing_names:
                click.echo(f"  Skipped: '{conn_name}' not found")
                continue
            if conn_name in connections:
                click.echo(f"  Skipped: '{conn_name}' already added")
                continue
            connections.append(conn_name)

    ptype = PersonType(person_type) if person_type else None
    p = create_person(name, company, ptype, background, linkedin, industry, revenue, headcount, connections)
    type_str = p.type.value if p.type else "person"
    click.echo(f"Created {type_str}: {p.name} @ {p.current_company}")
    if p.connections:
        click.echo(f"  Connections: {', '.join(p.connections)}")


@person.command("delete")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def person_delete(name: str, yes: bool):
    """Delete a person and their interactions."""
    p = get_person(name)
    if p is None:
        click.echo(f"Person '{name}' not found.")
        return

    if not yes:
        click.confirm(f"Delete '{name}' and all their interactions?", abort=True)

    delete_person(name)
    click.echo(f"Deleted: {name}")


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
    if p.company_industry:
        click.echo(f"Industry: {p.company_industry}")
    if p.company_revenue:
        click.echo(f"Revenue: {p.company_revenue}")
    if p.company_headcount:
        click.echo(f"Headcount: {p.company_headcount}")
    if p.type:
        click.echo(f"Type: {p.type.value}")
    if p.linkedin_url:
        click.echo(f"LinkedIn: {p.linkedin_url}")
    click.echo(f"Interactions: {len(p.interaction_ids)}")
    if p.connections:
        click.echo(f"Connections: {', '.join(p.connections)}")
    click.echo(f"{'='*60}")

    if p.background:
        click.echo(f"\nBackground:\n{p.background}")

    if p.last_delta:
        click.echo(f"\nLast Delta:\n{p.last_delta}")

    if p.state_of_play:
        click.echo(f"\nState of Play:\n{p.state_of_play}")

    click.echo()


@person.command("connect")
@click.argument("name_a", required=False)
@click.argument("name_b", required=False)
def person_connect(name_a: str | None, name_b: str | None):
    """Add a connection between two people."""
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import FuzzyWordCompleter

    persons = list_persons()
    if len(persons) < 2:
        click.echo("Need at least two people to create a connection.")
        return

    names = [p.name for p in persons]
    completer = FuzzyWordCompleter(names)

    if name_a is None:
        name_a = pt_prompt("First person (tab to complete): ", completer=completer).strip()
    if name_b is None:
        name_b = pt_prompt("Second person (tab to complete): ", completer=completer).strip()

    if name_a == name_b:
        click.echo("Cannot connect a person to themselves.")
        return

    for n in (name_a, name_b):
        if get_person(n) is None:
            click.echo(f"Person '{n}' not found.")
            return

    add_connection(name_a, name_b)
    click.echo(f"Connected: {name_a} <-> {name_b}")


@person.command("disconnect")
@click.argument("name_a", required=False)
@click.argument("name_b", required=False)
def person_disconnect(name_a: str | None, name_b: str | None):
    """Remove a connection between two people."""
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import FuzzyWordCompleter

    persons = list_persons()
    names = [p.name for p in persons]
    completer = FuzzyWordCompleter(names)

    if name_a is None:
        name_a = pt_prompt("First person (tab to complete): ", completer=completer).strip()
    if name_b is None:
        name_b = pt_prompt("Second person (tab to complete): ", completer=completer).strip()

    for n in (name_a, name_b):
        if get_person(n) is None:
            click.echo(f"Person '{n}' not found.")
            return

    if remove_connection(name_a, name_b):
        click.echo(f"Disconnected: {name_a} <-> {name_b}")
    else:
        click.echo(f"No connection found between '{name_a}' and '{name_b}'.")


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

    click.echo(f"\n{'Name':<25} {'Company':<25} {'Type':<12} {'Ixns':<6} {'Connections'}")
    click.echo("-" * 90)
    for p in persons:
        type_str = p.type.value if p.type else "-"
        conns_str = ", ".join(p.connections) if p.connections else "-"
        click.echo(f"{p.name:<25} {p.current_company:<25} {type_str:<12} {len(p.interaction_ids):<6} {conns_str}")
    click.echo()


@cli.group()
def interaction():
    """Manage interactions."""
    pass


@interaction.command("delete")
@click.option("--person", "-p", "person_name", default=None, help="Person name")
@click.option("--date", "-d", "date_str", default=None, help="Interaction date slug (e.g. 2025-09-05 or 2025-09-05_2)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def interaction_delete(person_name: str | None, date_str: str | None, yes: bool):
    """Delete an interaction by person and date slug.

    When multiple interactions share a date, they are shown as
    2025-09-05, 2025-09-05_2, 2025-09-05_3, etc. — matching the
    virtual filesystem convention.
    """
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import FuzzyWordCompleter
    from vfs import _build_date_slugs

    # Pick person with fuzzy completion
    if person_name is None:
        persons = list_persons()
        if not persons:
            click.echo("No people found.")
            return
        names = [p.name for p in persons]
        completer = FuzzyWordCompleter(names)
        person_name = pt_prompt("Person (tab to complete): ", completer=completer).strip()

    p = get_person(person_name)
    if p is None:
        click.echo(f"Person '{person_name}' not found.")
        return

    interactions = get_interactions(person_name)
    if not interactions:
        click.echo(f"No interactions found for '{person_name}'.")
        return

    # Build date slugs (same logic as VFS: date, date_2, date_3, ...)
    slug_map = _build_date_slugs(interactions)

    # Pick date slug with fuzzy completion
    if date_str is None:
        slugs = sorted(slug_map.keys())
        completer = FuzzyWordCompleter(slugs)
        date_str = pt_prompt("Date (tab to complete): ", completer=completer).strip()

    if date_str not in slug_map:
        click.echo(f"No interaction found for '{person_name}' with slug '{date_str}'.")
        return

    # Single interaction selected via slug
    interaction = slug_map[date_str]
    tags_str = ", ".join(t.value for t in interaction.tags)
    click.echo(f"\n  Interaction #{interaction.id} — {date_str} — Tags: {tags_str}")
    for t in interaction.takeaways:
        click.echo(f"    - {t}")

    if not yes:
        click.confirm(f"\nDelete interaction?", abort=True)

    delete_interaction(interaction.id)
    click.echo(f"Deleted interaction for '{person_name}' ({date_str}).")


@cli.command()
@click.argument("file_path", required=False, default=None, type=click.Path())
@click.option("--person", "-p", "person_name", default=None, help="Person name")
@click.option("--date", "-d", default=None, help="Date (YYYY-MM-DD), defaults to today")
def ingest(file_path: str | None, person_name: str | None, date: str | None):
    """Ingest a recording or transcript and process through the pipeline."""
    import os
    from config import TRANSCRIPT_EXTENSIONS, RECORDING_EXTENSIONS

    if file_path is None:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.completion import PathCompleter
        file_path = pt_prompt("File path (tab to complete): ", completer=PathCompleter()).strip()
    if not os.path.exists(file_path):
        click.echo(f"Error: Path '{file_path}' does not exist.")
        return

    ext = os.path.splitext(file_path)[1].lower()
    is_transcript = ext in TRANSCRIPT_EXTENSIONS
    if not is_transcript and ext not in RECORDING_EXTENSIONS:
        click.echo(
            f"Error: Unsupported file type '{ext}'. "
            f"Supported: {', '.join(sorted(TRANSCRIPT_EXTENSIONS | RECORDING_EXTENSIONS))}"
        )
        return

    if person_name is None:
        persons = list_persons()
        if persons:
            from prompt_toolkit import prompt as pt_prompt
            from prompt_toolkit.completion import FuzzyWordCompleter
            names = [p.name for p in persons]
            completer = FuzzyWordCompleter(names)
            person_name = pt_prompt("Person (tab to complete): ", completer=completer).strip()
        else:
            person_name = click.prompt("Person name")
    if date is None:
        date = click.prompt("Date (YYYY-MM-DD)", default=datetime.now().strftime("%Y-%m-%d"))

    interaction_date = None
    if date:
        interaction_date = datetime.strptime(date, "%Y-%m-%d")

    context = click.prompt(
        "Context about this conversation (optional, press Enter to skip)",
        default="",
        show_default=False,
    )

    try:
        if is_transcript:
            interaction = ingest_transcript(file_path, person_name, interaction_date, context)
        else:
            interaction = ingest_recording(file_path, person_name, interaction_date, context)

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
    """Search interactions, people, and text."""
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


@search.command("interactions")
@click.option("--tag", "tag_name", type=click.Choice(["pricing", "product", "gtm", "competitors", "market"]), help="Filter by tag")
@click.option("--type", "-t", "person_type", type=click.Choice(["customer", "investor", "competitor"]), help="Filter by person type")
@click.option("--company", help="Filter by company name (substring)")
@click.option("--industry", help="Filter by industry (substring)")
@click.option("--person", "person_name", help="Filter by person name")
@click.option("--text", help="Full-text search across takeaways and transcripts")
@click.option("--from", "date_from", help="Start date (YYYY-MM-DD)")
@click.option("--to", "date_to", help="End date (YYYY-MM-DD)")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table", help="Output format")
def search_interactions_cmd(tag_name, person_type, company, industry, person_name, text, date_from, date_to, fmt):
    """Search interactions with multiple filters."""
    import json as json_mod

    tag = Tag(tag_name) if tag_name else None
    ptype = PersonType(person_type) if person_type else None

    results = search_interactions(
        tag=tag, person_type=ptype, company=company, industry=industry,
        person_name=person_name, text=text, date_from=date_from, date_to=date_to,
    )

    if not results:
        click.echo("No interactions found.")
        return

    if fmt == "json":
        out = []
        for i in results:
            out.append({
                "id": i.id,
                "person_name": i.person_name,
                "date": i.date.strftime("%Y-%m-%d"),
                "tags": [t.value for t in i.tags],
                "takeaways": i.takeaways,
            })
        click.echo(json_mod.dumps(out, indent=2))
    else:
        click.echo(f"\n{len(results)} interaction(s) found:\n")
        for i in results:
            tags_str = ", ".join(t.value for t in i.tags)
            click.echo(f"[{i.date.strftime('%Y-%m-%d')}] {i.person_name} — {tags_str}")
            for t in i.takeaways:
                click.echo(f"  - {t}")
            click.echo()


@search.command("people")
@click.option("--type", "-t", "person_type", type=click.Choice(["customer", "investor", "competitor"]), help="Filter by person type")
@click.option("--company", help="Filter by company name (substring)")
@click.option("--industry", help="Filter by industry (substring)")
@click.option("--text", help="Full-text search across state of play and background")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table", help="Output format")
def search_people_cmd(person_type, company, industry, text, fmt):
    """Search people with filters."""
    import json as json_mod

    ptype = PersonType(person_type) if person_type else None

    results = search_persons(person_type=ptype, company=company, industry=industry, text=text)

    if not results:
        click.echo("No people found.")
        return

    if fmt == "json":
        out = []
        for p in results:
            out.append({
                "name": p.name,
                "company": p.current_company,
                "type": p.type.value if p.type else "",
                "industry": p.company_industry,
                "revenue": p.company_revenue,
                "headcount": p.company_headcount,
                "interactions": len(p.interaction_ids),
                "state_of_play": p.state_of_play,
            })
        click.echo(json_mod.dumps(out, indent=2))
    else:
        click.echo(f"\n{len(results)} person(s) found:\n")
        click.echo(f"{'Name':<25} {'Company':<25} {'Type':<12} {'Industry':<20} {'Ixns'}")
        click.echo("-" * 90)
        for p in results:
            type_str = p.type.value if p.type else "-"
            ind_str = p.company_industry or "-"
            click.echo(f"{p.name:<25} {p.current_company:<25} {type_str:<12} {ind_str:<20} {len(p.interaction_ids)}")
        click.echo()


@search.command("text")
@click.argument("query")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table", help="Output format")
def search_text_cmd(query, fmt):
    """Full-text search across all transcripts and takeaways."""
    import json as json_mod

    results = search_text(query)

    if not results:
        click.echo(f"No results for '{query}'.")
        return

    if fmt == "json":
        click.echo(json_mod.dumps(results, indent=2))
    else:
        click.echo(f"\n{len(results)} result(s) for '{query}':\n")
        for r in results:
            tags_str = ", ".join(r["tags"])
            click.echo(f"[{r['date']}] {r['person_name']} — {tags_str}")
            if r["matching_takeaways"]:
                for t in r["matching_takeaways"]:
                    click.echo(f"  - {t}")
            if r["transcript_quotes"]:
                for q in r["transcript_quotes"]:
                    click.echo(f"  Quote:")
                    for line in q.split("\n"):
                        click.echo(f"    {line}")
            click.echo()


@cli.group()
def aggregate():
    """Aggregate data across interactions and people."""
    pass


@aggregate.command("tags")
@click.option("--type", "-t", "person_type", type=click.Choice(["customer", "investor", "competitor"]), help="Filter by person type")
@click.option("--company", help="Filter by company name")
@click.option("--industry", help="Filter by industry")
@click.option("--from", "date_from", help="Start date (YYYY-MM-DD)")
@click.option("--to", "date_to", help="End date (YYYY-MM-DD)")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table", help="Output format")
def aggregate_tags_cmd(person_type, company, industry, date_from, date_to, fmt):
    """Show tag frequency distribution."""
    import json as json_mod

    ptype = PersonType(person_type) if person_type else None
    counts = aggregate_tags(
        person_type=ptype, company=company, industry=industry,
        date_from=date_from, date_to=date_to,
    )

    if not counts:
        click.echo("No interactions found.")
        return

    if fmt == "json":
        click.echo(json_mod.dumps(counts, indent=2))
    else:
        total = sum(counts.values())
        click.echo(f"\nTag distribution ({total} total):\n")
        click.echo(f"{'Tag':<16} {'Count':>6}  Bar")
        click.echo("-" * 40)
        max_count = max(counts.values()) if counts else 1
        for tag, count in counts.items():
            bar_len = int(count / max_count * 20)
            bar = "\u2588" * bar_len + "\u2591" * (20 - bar_len)
            click.echo(f"{tag:<16} {count:>6}  {bar}")
        click.echo()


@aggregate.command("segments")
@click.option("--by", "by_field", required=True, type=click.Choice(["type", "industry", "company"]), help="Field to group by")
@click.option("--type", "-t", "person_type", type=click.Choice(["customer", "investor", "competitor"]), help="Filter by person type")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table", help="Output format")
def aggregate_segments_cmd(by_field, person_type, fmt):
    """Group people and interactions by a field."""
    import json as json_mod

    ptype = PersonType(person_type) if person_type else None
    results = aggregate_segments(by_field=by_field, person_type=ptype)

    if not results:
        click.echo("No data found.")
        return

    if fmt == "json":
        click.echo(json_mod.dumps(results, indent=2))
    else:
        click.echo(f"\nSegments by {by_field}:\n")
        click.echo(f"{'Segment':<30} {'People':>7} {'Interactions':>13}")
        click.echo("-" * 55)
        for r in results:
            click.echo(f"{r['segment']:<30} {r['people']:>7} {r['interactions']:>13}")
        click.echo()


@cli.group()
def followup():
    """Manage follow-up action items."""
    pass


@followup.command("add")
@click.option("--person", "-p", "person_name", default=None, help="Person name")
@click.option("--date", "-d", "date_slugs", multiple=True, help="Date slug(s) to extract from (repeatable)")
@click.option("--all", "-a", "all_interactions", is_flag=True, help="Extract from all interactions")
def followup_add(person_name: str | None, date_slugs: tuple[str, ...], all_interactions: bool):
    """Extract follow-ups from existing interactions.

    Pick a person, then select which interactions to analyze.
    Uses AI to identify action items from the transcript(s).
    """
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import FuzzyWordCompleter
    from vfs import _build_date_slugs
    from services.analysis import extract_followups

    # Pick person
    if person_name is None:
        persons = list_persons()
        if not persons:
            click.echo("No people found.")
            return
        names = [p.name for p in persons]
        completer = FuzzyWordCompleter(names)
        person_name = pt_prompt("Person (tab to complete): ", completer=completer).strip()

    p = get_person(person_name)
    if p is None:
        click.echo(f"Person '{person_name}' not found.")
        return

    interactions = get_interactions(person_name)
    if not interactions:
        click.echo(f"No interactions found for '{person_name}'.")
        return

    slug_map = _build_date_slugs(interactions)

    # Select interactions
    if all_interactions:
        selected_slugs = list(slug_map.keys())
    elif date_slugs:
        selected_slugs = list(date_slugs)
        for s in selected_slugs:
            if s not in slug_map:
                click.echo(f"No interaction found for '{person_name}' with slug '{s}'.")
                return
    else:
        # Interactive: show interactions and let user pick
        sorted_slugs = sorted(slug_map.keys())
        click.echo(f"\nInteractions for {person_name}:\n")
        for slug in sorted_slugs:
            ix = slug_map[slug]
            tags_str = ", ".join(t.value for t in ix.tags)
            click.echo(f"  {slug}  Tags: {tags_str}")
        click.echo()
        completer = FuzzyWordCompleter(sorted_slugs)
        selected_slugs = []
        while True:
            choice = pt_prompt("Date slug to analyze (empty to finish): ", completer=completer).strip()
            if not choice:
                break
            if choice not in slug_map:
                click.echo(f"  '{choice}' not found, try again.")
                continue
            if choice in selected_slugs:
                click.echo(f"  '{choice}' already selected.")
                continue
            selected_slugs.append(choice)

    if not selected_slugs:
        click.echo("No interactions selected.")
        return

    # Extract followups from each selected interaction
    total_added = 0
    for slug in selected_slugs:
        ix = slug_map[slug]
        click.echo(f"\nExtracting follow-ups from {slug}...")
        items = extract_followups(ix.transcript, person_name, person_name)
        if items:
            create_followups(person_name, ix.id, slug, items)
            for item in items:
                click.echo(f"  - {item}")
            total_added += len(items)
        else:
            click.echo("  (no action items found)")

    click.echo(f"\nAdded {total_added} follow-up(s) for {person_name}.")


@followup.command("list")
@click.argument("name", required=False, default=None)
def followup_list(name: str | None):
    """List open follow-ups for a person."""
    if name is None:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.completion import FuzzyWordCompleter
        persons = list_persons()
        if not persons:
            click.echo("No people found.")
            return
        names = [p.name for p in persons]
        completer = FuzzyWordCompleter(names)
        name = pt_prompt("Person (tab to complete): ", completer=completer).strip()

    p = get_person(name)
    if p is None:
        click.echo(f"Person '{name}' not found.")
        return

    followups = get_open_followups(name)
    if not followups:
        click.echo(f"No open follow-ups for {name}.")
        return

    click.echo(f"\nOpen follow-ups for {name}:\n")
    for f in followups:
        click.echo(f"  [{f.id}] ({f.date_slug}) {f.item}")
    click.echo()


@followup.command("complete")
@click.argument("followup_id", required=False, default=None, type=int)
@click.option("--person", "-p", "person_name", default=None, help="Person name (interactive mode)")
def followup_complete(followup_id: int | None, person_name: str | None):
    """Mark a follow-up as complete.

    Direct mode: followup complete 2
    Interactive mode: followup complete --person "John Doe"
    """
    if followup_id is not None:
        # Direct mode: complete by ID
        f = complete_followup(followup_id)
        if f is None:
            click.echo(f"Followup #{followup_id} not found.")
            return
        click.echo(f'Completed: "{f.item}"')
        return

    # Interactive mode: pick person, show list, prompt for ID
    if person_name is None:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.completion import FuzzyWordCompleter
        persons = list_persons()
        if not persons:
            click.echo("No people found.")
            return
        names = [p.name for p in persons]
        completer = FuzzyWordCompleter(names)
        person_name = pt_prompt("Person (tab to complete): ", completer=completer).strip()

    p = get_person(person_name)
    if p is None:
        click.echo(f"Person '{person_name}' not found.")
        return

    followups = get_open_followups(person_name)
    if not followups:
        click.echo(f"No open follow-ups for {person_name}.")
        return

    click.echo(f"\nOpen follow-ups for {person_name}:\n")
    for f in followups:
        click.echo(f"  [{f.id}] ({f.date_slug}) {f.item}")

    chosen_id = click.prompt("\nFollowup ID to complete", type=int)
    f = complete_followup(chosen_id)
    if f is None:
        click.echo(f"Followup #{chosen_id} not found.")
        return
    click.echo(f'Completed: "{f.item}"')


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
