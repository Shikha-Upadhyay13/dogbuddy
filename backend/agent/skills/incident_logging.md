# Skill: Incident Logging

When a staff member reports something happened to a dog, log it as an incident.

## Severity guide
- **mild**: skipped meal, minor scuffle with no contact, mild limp, vomiting once
- **moderate**: physical altercation, refusing food >24h, persistent limping,
  diarrhea, unusual lethargy
- **severe**: injury with bleeding, seizure, suspected poisoning, dog attack,
  prolonged vomiting, unresponsive

## Required fields
- `dog_id`: which dog
- `type`: health / behavior / feeding / other
- `severity`: as above
- `description`: clear, factual, what happened (no opinions)

## Response pattern
1. Confirm the dog (look up by name → get id)
2. Confirm severity based on description
3. Log via the log_incident tool
4. Reply with: "Logged for [dog name] — [type], [severity]. {next-action if needed}"
5. For severe incidents, add: "This sounds serious. Notify the manager and consider calling the vet."
