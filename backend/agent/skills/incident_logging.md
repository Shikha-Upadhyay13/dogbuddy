# Skill: Incident Logging

When a staff member reports something happened to a dog, log it as an incident.

## Severity guide
- **mild**: minor scuffle with no contact, very small scrape
- **moderate**: skipped meal, mild limp, vomiting once, refusing food, mild
  lethargy, minor stomach upset
- **severe**: persistent limping, diarrhea, dog attack, seizure, suspected
  poisoning, prolonged vomiting, unresponsive, injury with bleeding

## Required fields
- `dog_id`: which dog
- `type`: health / behavior / feeding / other
- `severity`: as above
- `description`: clear, factual, what happened (no opinions)

## Response pattern
1. Confirm the dog (look up by name → get id)
2. Pick severity based on description
3. Log via the log_incident tool right away
4. Reply with: "Logged for [dog name] — [type], [severity]."
5. For severe incidents, you can add a brief note suggesting the staff
   notify the manager if they want.
