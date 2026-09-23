# Dataset interpretation notes

The official JSON and CSV files remain unchanged. Their snapshot date,
`2026-10-01`, is the application's reference date; imported snapshots supply
their own date through consistent JSON metadata.

## Recurring mandatory training

The README says completed events cannot be repeated except for club `EV_036`.
The supplied history also repeats mandatory compliance events `EV_001`, `EV_002`
and `EV_003`, whose descriptions identify annual training. Validation therefore
allows recurring mandatory compliance and the club. One-time events, including
onboarding, cannot have multiple completed records for the same employee.

## Skill gains and caps

The README specifies an increase by `gain`, capped at `max_level`. The application
interprets that as `max(current, min(current + gain, max_level))`: an introductory
event cannot lower an already higher skill. This is an explicit implementation
interpretation, rather than an additional field in the dataset.

Assessed employee skills remain the baseline at `last_review_date`. Completed
activities after that assessment are projected separately. Missing assessed
skills start at zero; historical prerequisites are not inferred from today's
assessed levels or current role.

## Completion dates and ordering

The CSV `date` is a scheduled session date or, for self-paced events, an enrollment
or assignment date. It does not provide an exact completion timestamp. Historical
projection uses that available date as its documented approximation and a
deterministic order for ties. Caps can make the order of skill gains matter.

Runtime completion preserves the original `date` and records `completed_on` as
an extension. The importer accepts an optional `completed_on` CSV column; the
official required columns stay the same. Runtime state records live completion
information so a completion on the assessment date can be applied exactly once.
For multiple live completions on one day, their transaction order is persisted
and replayed, including after restart. Historical ties use record IDs because
the source supplies no more precise ordering.

Validation rejects later participation after a known completion for scheduled
events or when `completed_on` is explicit. It does not infer that ordering from
a historical self-paced enrollment date. Duplicate completions of one-time
events are still rejected.

## Schema and tenure

JSON documents retain their official envelopes and must agree on dataset name,
version and snapshot date. Skill levels are strict integers from 0 through 5;
booleans, numeric strings and fractional values are rejected. Identifiers must
be unique, references must resolve, and critical skills must have required
levels in their role profile.

`tenure_months` means full calendar months from `hire_date` to the snapshot date:
`12 * (snapshot.year - hire.year) + snapshot.month - hire.month`, minus one when
the snapshot day of the month is earlier than the hire day. The importer checks
that supplied value against the documented definition.

CSV uses UTF-8, accepts a BOM, reordered columns and quoted multiline values,
and rejects missing, repeated or unknown columns. Schema and relationship errors
are returned with a code, location and message. Appending accepts additional
profiles and history; changing catalogs requires a complete validated snapshot.
