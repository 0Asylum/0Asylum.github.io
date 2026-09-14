# GANG GANG site

Open `index.html`, or run `python3 -m http.server 8000` here and visit
`http://localhost:8000`. The header uses the animated banner; reduced-motion
visitors see its still PNG.

To refresh HTB stats and the roster, run `python3 scripts/refresh_site.py`.
It reads the sibling bot database without copying it here. Add only
member-approved public details to `data/member-extras.json`, keyed by HTB ID:

```json
{
  "66289": {
    "bio": "A short public bio",
    "links": [{"label": "GitHub", "url": "https://github.com/example"}]
  }
}
```

Unset fields produce no visible placeholder. Rank colors are consistent for
each HTB rank. The captain appears first, founder `opr3vail` second, then
other members follow by rank and points. The site currently has 15 HTB
avatars, two custom Discord avatars for claimed
members with no HTB image, and three initials fallbacks.

Never copy the database, bot configuration, logs, Discord identifiers, or
credentials into this site. Review generated pages and assets before any
commit or deployment.
