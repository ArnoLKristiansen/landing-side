import json, os, sqlite3
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('FORBRUG_DATA', ROOT / 'data'))
def now(): return datetime.now(timezone.utc).isoformat()
def connect():
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    c = sqlite3.connect(DATA / 'usage.sqlite3', timeout=20)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS events (
      id TEXT PRIMARY KEY, source TEXT NOT NULL, timestamp TEXT NOT NULL,
      day TEXT NOT NULL, task TEXT NOT NULL, program TEXT NOT NULL,
      function TEXT NOT NULL, model TEXT NOT NULL,
      input INTEGER NOT NULL, cached INTEGER NOT NULL, output INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS labels (task TEXT PRIMARY KEY, program TEXT, function TEXT);
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    ''')
    return c
def put(c, key, value):
    c.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key,json.dumps(value)))
def get(c, key, default=None):
    r=c.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
    return json.loads(r[0]) if r else default
def import_events(payload):
    with connect() as c:
        for e in payload.get('events',[]):
            if e['source'] not in ('codex','api_tracked','api_org'): raise ValueError('Ukendt kilde')
            for k in ('input','cached','output'):
                if type(e[k]) is not int or e[k]<0: raise ValueError('Ugyldigt tokenantal')
            if e['cached']>e['input']: raise ValueError('Cache overstiger input')
            c.execute('INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?)',
              tuple(e[k] for k in ('id','source','timestamp','day','task','program','function','model','input','cached','output')))
        if payload.get('limits'):
            old=get(c,'limits',{})
            if payload['limits'].get('observed_at','') >= old.get('observed_at',''):
                put(c,'limits',payload['limits'])
        if payload.get('account_usage'): put(c,'account_usage',payload['account_usage'])
        if payload.get('collector'): put(c,'collector',{'at':now(), **payload['collector']})
    return len(payload.get('events',[]))
