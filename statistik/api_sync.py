"""Read-only organization usage import. Requires a separately configured Admin API key."""
import hashlib, json, time
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from storage import DATA, connect, put, now

def sync():
    keyfile=DATA/'openai-admin-key'
    if not keyfile.exists():
        with connect() as c: put(c,'api_status',{'state':'not_connected','message':'OpenAI API er ikke tilsluttet. Der er endnu ikke konfigureret en Admin API-nøgle.'})
        return
    key=keyfile.read_text().strip()
    start=int((datetime.now(timezone.utc)-timedelta(days=90)).replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
    end=int(time.time()); events=[]
    for endpoint in ('completions','embeddings'):
        page=None
        while True:
            q=[('start_time',start),('end_time',end),('bucket_width','1d'),('limit',31),('group_by','project_id'),('group_by','model')]
            if page:q.append(('page',page))
            req=Request('https://api.openai.com/v1/organization/usage/'+endpoint+'?'+urlencode(q),headers={'Authorization':'Bearer '+key})
            with urlopen(req,timeout=30) as r: payload=json.load(r)
            for b in payload['data']:
                ts=datetime.fromtimestamp(b['start_time'],timezone.utc).isoformat(); day=ts[:10]
                for x in b['results']:
                    project=x.get('project_id') or 'Uden projekt'; model=x.get('model') or 'Ukendt model'
                    identity=f'{endpoint}:{day}:{project}:{model}'
                    events.append(('api-org:'+hashlib.sha256(identity.encode()).hexdigest(),'api_org',ts,day,
                      'api-project:'+project,project,'Ikke fordelt på funktion',model,x.get('input_tokens',0),x.get('input_cached_tokens',0),x.get('output_tokens',0)))
            if not payload.get('has_more'):break
            page=payload.get('next_page')
            if not page:raise ValueError('Missing pagination cursor')
    # Replace fetched date range only after all pages and endpoints succeeded.
    with connect() as c:
        c.execute('DELETE FROM events WHERE source=? AND day>=?',('api_org',datetime.fromtimestamp(start,timezone.utc).date().isoformat()))
        c.executemany('INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?)',events)
        put(c,'api_status',{'state':'connected','at':now(),'message':'OpenAI organisationsdata: tekst/modelkald og embeddings, seneste 90 dage. Dage følger UTC. Andre API-produkter er ikke med.'})

if __name__=='__main__': sync()
