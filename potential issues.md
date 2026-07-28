# Potential issues

## Duplicate companies in identity review

The identity review list currently renders one row per open identity-resolution case. That means the same company can appear more than once when separate observations have been created for it.

### Likely root cause

- Source observations are intentionally created per discovery event or scout persona.
- The current open-case uniqueness rule prevents duplicate cases for the same observation, but not for the same company, domain, or provider identity.
- Repeated discoveries, manual lookups, and imports can therefore create multiple observations for one real company.
- The frontend is faithfully rendering each case by its unique identity-case ID rather than grouping cases by a canonical company identity.

### Recommended fix

1. Normalize reliable identity keys first, prioritizing verified domain and provider IDs over company name.
2. Introduce a relationship between one identity case and all observations that refer to that identity.
3. Group the review list by canonical identity, showing the number of supporting observations and their sources.
4. Resolve or reject the grouped identity together, transitioning all linked observations consistently.
5. Keep observations with only an ambiguous name match separate until a human confirms they are the same company.

The UI should not simply hide duplicate names. That would make the list look cleaner while leaving the underlying identity graph inconsistent.
