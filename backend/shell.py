"""Interactive REPL shell with filesystem-style navigation."""

import os
import shlex
from datetime import datetime
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.completion import FuzzyWordCompleter
from prompt_toolkit.history import FileHistory

import vfs
from config import PersonType, Tag, TAG_DESCRIPTIONS
from database import (
    complete_followup,
    create_person,
    get_interactions_by_tag,
    get_open_followups,
    get_person,
    init_db,
    list_persons,
)
from services.ingestion import ingest_recording


COMMANDS = ["ls", "cd", "cat", "tree", "pwd", "clear", "ingest", "mkperson", "search", "tags", "followups", "complete", "help", "exit"]


class RolodexCompleter(Completer):
    """Tab completion aware of virtual filesystem paths and commands."""

    def __init__(self, shell: "RolodexShell"):
        self.shell = shell

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        words = text.split()

        # Complete command name
        if len(words) == 0 or (len(words) == 1 and not text.endswith(" ")):
            partial = words[0] if words else ""
            for cmd in COMMANDS:
                if cmd.startswith(partial):
                    yield Completion(cmd, start_position=-len(partial))
            return

        # Complete paths for ls, cd, cat, tree
        if words[0] in ("ls", "cd", "cat", "tree"):
            partial = words[-1] if len(words) > 1 and not text.endswith(" ") else ""
            if text.endswith(" "):
                partial = ""

            # Determine the directory to list completions from
            if "/" in partial:
                last_slash = partial.rfind("/")
                dir_part = partial[: last_slash + 1] if last_slash >= 0 else ""
                name_part = partial[last_slash + 1 :]
            else:
                dir_part = ""
                name_part = partial

            if dir_part:
                dir_path = vfs.resolve_path(self.shell.cwd, dir_part)
            else:
                dir_path = self.shell.cwd

            node = vfs.resolve(dir_path)
            if node is None or not node.is_dir:
                return

            for child in node.children:
                if child.startswith(name_part):
                    yield Completion(
                        dir_part + child,
                        start_position=-len(partial),
                    )


class RolodexShell:
    """Interactive REPL with filesystem-style navigation."""

    def __init__(self):
        init_db()
        self.cwd = "/"
        history_path = Path.home() / ".rolodex_history"
        self.session: PromptSession = PromptSession(
            history=FileHistory(str(history_path)),
            completer=RolodexCompleter(self),
        )

    def get_prompt(self) -> str:
        return f"rolodex:{self.cwd}$ "

    def run(self) -> None:
        """Main REPL loop."""
        print("Rolodex Shell — type 'help' for commands, 'exit' to quit")
        while True:
            try:
                text = self.session.prompt(self.get_prompt()).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not text:
                continue

            try:
                args = shlex.split(text)
            except ValueError as e:
                print(f"Parse error: {e}")
                continue

            cmd = args[0]
            cmd_args = args[1:]

            handler = getattr(self, f"cmd_{cmd}", None)
            if handler is None:
                print(f"Unknown command: {cmd}")
                continue

            try:
                handler(cmd_args)
            except Exception as e:
                print(f"Error: {e}")

    # ── Commands ──────────────────────────────────────────────

    def cmd_pwd(self, args: list[str]) -> None:
        print(self.cwd)

    def cmd_ls(self, args: list[str]) -> None:
        target = args[0] if args else "."
        path = vfs.resolve_path(self.cwd, target)
        node = vfs.resolve(path)

        if node is None:
            print(f"ls: cannot access '{target}': No such file or directory")
            return

        if not node.is_dir:
            print(node.name)
            return

        for child in node.children:
            print(child)

    def cmd_cd(self, args: list[str]) -> None:
        target = args[0] if args else "/"
        path = vfs.resolve_path(self.cwd, target)
        node = vfs.resolve(path)

        if node is None:
            print(f"cd: no such directory: {target}")
            return

        if not node.is_dir:
            print(f"cd: not a directory: {target}")
            return

        self.cwd = node.path

    def cmd_cat(self, args: list[str]) -> None:
        if not args:
            print("Usage: cat <path>")
            return

        target = args[0]
        path = vfs.resolve_path(self.cwd, target)
        node = vfs.resolve(path)

        if node is None:
            print(f"cat: {target}: No such file or directory")
            return

        if node.is_dir:
            print(f"cat: {target}: Is a directory")
            return

        print(node.content)

    def cmd_tree(self, args: list[str]) -> None:
        target = args[0] if args else "."
        path = vfs.resolve_path(self.cwd, target)
        print(vfs.tree(path))

    def cmd_clear(self, args: list[str]) -> None:
        os.system("cls" if os.name == "nt" else "clear")

    def cmd_ingest(self, args: list[str]) -> None:
        if len(args) < 1:
            print("Usage: ingest <video_path> --person <name> [--date YYYY-MM-DD]")
            return

        video_path = args[0]
        person_name = None
        date = None

        i = 1
        while i < len(args):
            if args[i] in ("--person", "-p") and i + 1 < len(args):
                person_name = args[i + 1]
                i += 2
            elif args[i] in ("--date", "-d") and i + 1 < len(args):
                date = args[i + 1]
                i += 2
            else:
                print(f"Unknown option: {args[i]}")
                return

        if person_name is None:
            print("Error: --person is required")
            return

        interaction_date = None
        if date:
            interaction_date = datetime.strptime(date, "%Y-%m-%d")

        interaction = ingest_recording(video_path, person_name, interaction_date)
        print(f"\nTakeaways:")
        for t in interaction.takeaways:
            print(f"  - {t}")
        print(f"\nTags: {', '.join(t.value for t in interaction.tags)}")

    def cmd_mkperson(self, args: list[str]) -> None:
        """Create a new person. Only name and company are required."""
        name = None
        company = None
        person_type = ""
        background = ""
        linkedin_url = ""
        company_industry = ""
        company_revenue = ""
        company_headcount = ""
        connections = []

        # Parse provided arguments
        if args:
            name = args[0]
            i = 1
            while i < len(args):
                if args[i] in ("--company", "-c") and i + 1 < len(args):
                    company = args[i + 1]
                    i += 2
                elif args[i] in ("--type", "-t") and i + 1 < len(args):
                    person_type = args[i + 1]
                    i += 2
                elif args[i] in ("--background", "-b") and i + 1 < len(args):
                    background = args[i + 1]
                    i += 2
                elif args[i] in ("--linkedin", "-l") and i + 1 < len(args):
                    linkedin_url = args[i + 1]
                    i += 2
                elif args[i] in ("--industry", "-i") and i + 1 < len(args):
                    company_industry = args[i + 1]
                    i += 2
                elif args[i] in ("--revenue", "-r") and i + 1 < len(args):
                    company_revenue = args[i + 1]
                    i += 2
                elif args[i] in ("--headcount", "-h") and i + 1 < len(args):
                    company_headcount = args[i + 1]
                    i += 2
                elif args[i] in ("--connection", "--conn") and i + 1 < len(args):
                    connections.append(args[i + 1])
                    i += 2
                else:
                    print(f"Unknown option: {args[i]}")
                    return

        # Prompt for missing required fields
        if name is None:
            name = self.session.prompt("Name: ").strip()
            if not name:
                print("Error: name cannot be empty")
                return

        if company is None:
            company = self.session.prompt("Company: ").strip()
            if not company:
                print("Error: company cannot be empty")
                return

        # Validate type if provided
        valid_types = [pt.value for pt in PersonType]
        if person_type and person_type not in valid_types:
            print(f"Error: type must be one of {valid_types}")
            return

        # Interactive connection loop
        persons = list_persons()
        existing_names = [p.name for p in persons]
        if existing_names:
            completer = FuzzyWordCompleter(existing_names)
            while True:
                conn_name = self.session.prompt(
                    "Connection (empty to finish): ",
                    completer=completer,
                ).strip()
                if not conn_name:
                    break
                if conn_name == name:
                    print("  Skipped: cannot connect a person to themselves")
                    continue
                if conn_name not in existing_names:
                    print(f"  Skipped: '{conn_name}' not found")
                    continue
                if conn_name in connections:
                    print(f"  Skipped: '{conn_name}' already added")
                    continue
                connections.append(conn_name)

        ptype = PersonType(person_type) if person_type else None
        p = create_person(name, company, ptype, background, linkedin_url, company_industry, company_revenue, company_headcount, connections)
        type_str = p.type.value if p.type else "person"
        print(f"Created {type_str}: {p.name} @ {p.current_company}")
        if p.connections:
            print(f"  Connections: {', '.join(p.connections)}")

    def cmd_followups(self, args: list[str]) -> None:
        """List open follow-ups for a person."""
        person_name = args[0] if args else None

        # Infer person from cwd if inside a person directory
        if person_name is None:
            parts = [p for p in self.cwd.split("/") if p]
            if parts:
                person_name = vfs._slug_to_name(parts[0])

        if person_name is None:
            print("Usage: followups [person]")
            return

        p = get_person(person_name)
        if p is None:
            print(f"Person '{person_name}' not found.")
            return

        followups = get_open_followups(person_name)
        if not followups:
            print(f"No open follow-ups for {person_name}.")
            return

        print(f"\nOpen follow-ups for {person_name}:\n")
        for f in followups:
            print(f"  [{f.id}] ({f.date_slug}) {f.item}")
        print()

    def cmd_complete(self, args: list[str]) -> None:
        """Mark a follow-up as complete."""
        if args:
            # Direct mode: complete <id>
            try:
                followup_id = int(args[0])
            except ValueError:
                print("Usage: complete <followup_id>")
                return
            f = complete_followup(followup_id)
            if f is None:
                print(f"Followup #{followup_id} not found.")
                return
            print(f'Completed: "{f.item}"')
            return

        # Interactive mode: infer person from cwd, show list, prompt
        person_name = None
        parts = [p for p in self.cwd.split("/") if p]
        if parts:
            person_name = vfs._slug_to_name(parts[0])

        if person_name is None:
            print("Usage: complete <followup_id>  (or cd into a person directory first)")
            return

        p = get_person(person_name)
        if p is None:
            print(f"Person '{person_name}' not found.")
            return

        followups = get_open_followups(person_name)
        if not followups:
            print(f"No open follow-ups for {person_name}.")
            return

        print(f"\nOpen follow-ups for {person_name}:\n")
        for f in followups:
            print(f"  [{f.id}] ({f.date_slug}) {f.item}")

        chosen = self.session.prompt("\nFollowup ID to complete: ").strip()
        try:
            followup_id = int(chosen)
        except ValueError:
            print("Invalid ID.")
            return

        f = complete_followup(followup_id)
        if f is None:
            print(f"Followup #{followup_id} not found.")
            return
        print(f'Completed: "{f.item}"')

    def cmd_search(self, args: list[str]) -> None:
        if len(args) < 2:
            print("Usage: search tag <tag_name>")
            return

        if args[0] == "tag":
            tag_name = args[1]
            valid_tags = [t.value for t in Tag]
            if tag_name not in valid_tags:
                print(f"Error: tag must be one of {valid_tags}")
                return

            tag = Tag(tag_name)
            interactions = get_interactions_by_tag(tag)

            if not interactions:
                print(f"No interactions found with tag '{tag_name}'.")
                return

            print(f"\nInteractions tagged '{tag_name}' ({TAG_DESCRIPTIONS[tag]}):\n")
            for interaction in interactions:
                print(f"[{interaction.date.strftime('%Y-%m-%d')}] {interaction.person_name}")
                for t in interaction.takeaways:
                    print(f"  - {t}")
                print()
        else:
            print(f"Unknown search type: {args[0]}")

    def cmd_tags(self, args: list[str]) -> None:
        print("\nAvailable Tags:\n")
        for tag in Tag:
            print(f"  {tag.value:<12} - {TAG_DESCRIPTIONS[tag]}")
        print()

    def cmd_help(self, args: list[str]) -> None:
        print("""
Commands:
  ls [path]                            List directory contents
  cd [path]                            Change directory
  cat <path>                           Show file contents
  tree [path]                          Show directory tree
  pwd                                  Print working directory
  clear                                Clear the screen
  ingest <file> --person <name>        Ingest a recording
  mkperson [name] [options]            Create a person (prompts for missing fields)
  search tag <tag>                     Search interactions by tag
  tags                                 List available tags
  followups [person]                   List open follow-ups (infers person from cwd)
  complete [id]                        Mark a follow-up complete (interactive if no id)
  help                                 Show this help
  exit                                 Exit the shell

mkperson options:
  --company, -c <company>              Person's company
  --type, -t <type>                    customer, investor, or competitor
  --background, -b <bio>               Optional background info
  --linkedin, -l <url>                 LinkedIn profile URL
  --industry, -i <industry>            Company industry
  --connection, --conn <name>          Connect to existing person (repeatable)
""")

    def cmd_exit(self, args: list[str]) -> None:
        raise EOFError
