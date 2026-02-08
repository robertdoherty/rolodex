# Search Dimensions

What the agent can filter and search on.

| Dimension | Source | CLI Flag | Search Type |
|-----------|--------|----------|-------------|
| Person Type | `Person.type` | `--type` | Enum: customer, investor, competitor |
| Company Name | `Person.current_company` | `--company` | Substring match |
| Company Revenue | `Person.company_revenue` | `--revenue` | Text field |
| Company Headcount | `Person.company_headcount` | `--headcount` | Text field |
| Industry | `Person.company_industry` | `--industry` | Substring match |
| Tags | `Interaction.tags` | `--tag` | Enum: pricing, product, gtm, competitors, market |
| Person Name | `Person.name` | `--person` | Substring match |
| Date Range | `Interaction.date` | `--from` / `--to` | YYYY-MM-DD |
| Takeaways | `Interaction.takeaways` | `--text` | Full-text search (FTS5) |
| Transcript | `Interaction.transcript` | `--text` | Full-text search (FTS5) |
| State of Play | `Person.state_of_play` | `--text` (people search) | Full-text search (FTS5) |
| Background | `Person.background` | `--text` (people search) | Full-text search (FTS5) |

## Command Reference

### search interactions
All flags: `--tag`, `--type`, `--company`, `--industry`, `--person`, `--text`, `--from`, `--to`, `--format`

### search people
All flags: `--type`, `--company`, `--industry`, `--text`, `--format`

### search text
Positional: QUERY (the search term)
Flags: `--format`

### aggregate tags
Flags: `--type`, `--company`, `--industry`, `--from`, `--to`, `--format`

### aggregate segments
Required: `--by` (type, industry, or company)
Flags: `--type`, `--format`
