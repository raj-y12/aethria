# CRM projection v1

`crm_projection_v1` is Aethria’s provider-neutral, current-state boundary for
external fund CRMs. It is built from canonical company, opportunity, people,
recommendation, ruling, evaluation, memo, and bounded provenance records. It
does not expose `scout_info`, `review_info`, `partner_info`, `agent_trace`, raw
claims, prompts, or internal evidence structures.

## Field authority

| Projection area | Canonical source | Semantics | External sync |
| --- | --- | --- | --- |
| Company IDs/name/domain | `companies` | current canonical identity | safe |
| Opportunity IDs/workflow | `opportunities` | current operational state | safe |
| Sector/geography | canonical company metadata | factual when present; optional | safe when present |
| Founders | `people`, `company_people`, bounded history | compact current identity view; unresolved stays explicit | safe |
| Recommendation | `recommendations` | Aethria’s current derived recommendation | safe |
| Human ruling | `human_rulings` | separate human/fund disposition | safe |
| Strengths/risks | recommendation drivers and risks | bounded derived summary | safe |
| Evaluation | `evaluation_runs` | specific current evaluation episode | reference only |
| Memo | memo identifier/reference | navigation pointer, not memo internals | safe |
| Provenance | selected source references | bounded audit/navigation references | safe |

Recommendation and ruling are never collapsed. For example, a CRM can show
`MONITOR` as Aethria’s recommendation and `INVEST` as the human ruling.

## External mappings

`external_entity_mappings` maps a tenant’s canonical company, person, or
opportunity ID to an external provider/workspace/object ID. The mapping is
metadata, not identity. The database prevents two Aethria entities from sharing
one external object within the same provider/workspace/entity type, and prevents
an Aethria entity from silently changing external objects. A remap must retire
the old mapping explicitly.

## Compatibility and future ingest

The existing approval-gated CSV export and workflow actions remain unchanged.
The new projection is the provider-neutral contract for future adapters. A
future CRM inbound envelope is tenant-private and may contain pipeline stage,
owner, meeting notes, relationship history, and private notes. No automatic
ingestion, OAuth, webhook, or bidirectional sync exists in Step 10.
