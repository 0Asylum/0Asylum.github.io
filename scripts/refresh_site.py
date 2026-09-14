"""Refresh the public static roster from the sibling bot database.

Usage: python3 scripts/refresh_site.py [path/to/database.db]
Only add member-supplied, public details to data/member-extras.json.
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DB = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (ROOT.parent / 'ggasylum' / 'database.db')
PAGE = ROOT / 'index.html'
EXTRAS = ROOT / 'data' / 'member-extras.json'
CAPTAIN_HTB_ID = 66289
FOUNDER_HTB_ID = 1775303


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def region(page: str, label: str, content: str) -> str:
    start = f'<!-- BEGIN GENERATED {label} -->'
    end = f'<!-- END GENERATED {label} -->'
    marker = re.search(r'(?m)^([ \t]*)' + re.escape(start), page)
    if not marker:
        raise ValueError(f'Missing {label} start marker in index.html')
    indent = marker.group(1)
    pattern = re.escape(start) + r'.*?' + re.escape(end)
    replacement = f'{start}\n{content}\n{indent}{end}'
    result, count = re.subn(pattern, lambda _: replacement, page, count=1, flags=re.S)
    if count != 1:
        raise ValueError(f'Missing or duplicate {label} markers in index.html')
    return result


def external_link(label: str, url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f'Invalid public HTTPS link for {label!r}')
    if any(ord(char) < 32 for char in url):
        raise ValueError(f'Control character in link for {label!r}')
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">&gt; {esc(label)}</a>'


def member_card(user: sqlite3.Row, extra: dict) -> str:
    uid = int(user['id'])
    name = str(extra.get('display_name') or user['name'])
    captain = uid == CAPTAIN_HTB_ID
    founder = uid == FOUNDER_HTB_ID
    rank_class = re.sub(r'[^a-z0-9]+', '-', str(user['rank'] or '').lower()).strip('-')
    custom_avatar = extra.get('avatar')
    if custom_avatar:
        asset = Path(custom_avatar)
        if asset.is_absolute() or '..' in asset.parts or asset.parts[:2] != ('assets', 'avatars') or not (ROOT / asset).is_file():
            raise ValueError(f'Invalid avatar asset for HTB user {uid}')
        avatar_src = asset.as_posix()
    else:
        avatar_src = next((f'assets/avatars/{filename}' for filename in (f'{uid}.png', f'{uid}-discord.png')
                           if (ROOT / 'assets' / 'avatars' / filename).is_file()), None)
    if avatar_src:
        avatar = f'<img src="{esc(avatar_src)}" alt="" loading="lazy">'
    else:
        initials = ''.join(part[:1] for part in re.split(r'[^A-Za-z0-9]+', name) if part)[:2].upper() or '?'
        avatar = f'<span class="avatar-fallback" aria-hidden="true">{esc(initials)}</span>'

    bio = extra.get('bio')
    bio_html = f'\n          <p class="member-bio">{esc(bio)}</p>' if isinstance(bio, str) and bio.strip() else ''
    links = [external_link('HTB profile', f'https://app.hackthebox.com/users/{uid}')]
    for link in extra.get('links', []):
        if not isinstance(link, dict) or not link.get('label') or not link.get('url'):
            raise ValueError(f'Invalid link entry for HTB user {uid}')
        links.append(external_link(str(link['label']), str(link['url'])))
    link_html = '\n            '.join(links)

    badge = (' <span class="captain-mark">★ captain</span>' if captain else
             ' <span class="founder-mark">★ Founder</span>' if founder else '')
    return f'''      <article class="member-card{' captain' if captain else ''}{' founder' if founder else ''}{' rank-' + rank_class if rank_class else ''}">
        <div class="member-avatar">{avatar}</div>
        <div class="member-body">
          <h3 class="member-name">{esc(name)}{badge}</h3>
          <span class="member-role">{esc(user['rank'] or 'HTB member')}</span>{bio_html}
          <div class="member-metrics" aria-label="Hack The Box stats">
            <div><strong>{int(user['points'] or 0):,}</strong><span>HTB pts</span></div>
            <div><strong>{int(user['system_owns'] or 0):,}</strong><span>root flags</span></div>
            <div><strong>{int(user['challenges'] or 0):,}</strong><span>puzzles</span></div>
          </div>
          <div class="member-links">
            {link_html}
          </div>
        </div>
      </article>'''


def main() -> None:
    extras = json.loads(EXTRAS.read_text(encoding='utf-8'))
    if not isinstance(extras, dict):
        raise ValueError('member-extras.json must be an object keyed by HTB ID')
    with sqlite3.connect(f'{DB.as_uri()}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        users = db.execute('''
            SELECT u.id, u.name, u.rank, u.rank_id, u.points, u.system_owns,
                   (SELECT count(*) FROM user_challenge_solves c WHERE c.user_id = u.id) AS challenges
              FROM users u
             ORDER BY CASE WHEN u.id = ? THEN 0 WHEN u.id = ? THEN 1 ELSE 2 END,
                      u.rank_id DESC, u.points DESC, lower(u.name), u.id
        ''', (CAPTAIN_HTB_ID, FOUNDER_HTB_ID)).fetchall()
        counts = dict(db.execute('SELECT type, count(*) FROM team_activity GROUP BY type').fetchall())
        dates = db.execute('SELECT min(date), max(date) FROM team_activity').fetchone()
        syncs = db.execute('SELECT min(last_synced_at), max(last_synced_at) FROM users').fetchone()
    if not users:
        raise ValueError('No team members found in database')
    known_ids = {str(user['id']) for user in users}
    unknown_ids = set(extras) - known_ids
    if unknown_ids:
        raise ValueError(f'Unknown HTB IDs in member-extras.json: {sorted(unknown_ids)}')

    page = PAGE.read_text(encoding='utf-8')
    stats = f'''  <section class="stats" aria-label="Team activity from Hack The Box">
    <div class="stat"><div class="stat-value">{len(users)}</div><div class="stat-label">Operatives</div></div>
    <div class="stat"><div class="stat-value">{counts.get('root', 0):,}</div><div class="stat-label">Root events</div></div>
    <div class="stat"><div class="stat-value">{counts.get('challenge', 0):,}</div><div class="stat-label">Puzzle clears</div></div>
    <div class="stat"><div class="stat-value">{counts.get('fortress', 0):,}</div><div class="stat-label">Fortress flags</div></div>
  </section>'''
    page = region(page, 'STATS', stats)
    page = region(page, 'MEMBERS', '\n'.join(member_card(user, extras.get(str(user['id']), {})) for user in users))
    page = region(page, 'NOTE', f'''    <p class="data-note">Team event counters cover {esc(dates[0][:10])}–{esc(dates[1][:10])} UTC. Profile stats are a bot snapshot; individual syncs range from {esc(syncs[0][:10])} to {esc(syncs[1][:10])}.</p>''')
    page, count = re.subn(r'<span class="count">\d+ members</span>', f'<span class="count">{len(users)} members</span>', page, count=1)
    if count != 1:
        raise ValueError('Missing roster count in index.html')
    PAGE.write_text(page, encoding='utf-8')
    print(f'Refreshed {len(users)} public HTB member cards')


if __name__ == '__main__':
    main()
