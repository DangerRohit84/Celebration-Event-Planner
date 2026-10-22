# Sample event fixtures

JSON payloads matching `POST /events` body. Use for live demo / seeding:

```bash
curl -X POST http://localhost:8000/events -H "Content-Type: application/json" -d @fixtures/wedding.json
```

Files:
- `wedding.json` — 150-guest royal garden wedding
- `birthday.json` — 40-guest superhero birthday
- `community.json` — 300-guest Diwali mela
