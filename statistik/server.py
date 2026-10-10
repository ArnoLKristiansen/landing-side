import argparse, calendar, json, math, os, sys, threading, time
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from storage import ROOT, connect, get, put, now, import_events
from zoneinfo import ZoneInfo
from credit_summary import credit_summary

def next_renewal(day, today=None):
    today=today or datetime.now(ZoneInfo('Europe/Copenhagen')).date()
    result=date(today.year,today.month,min(day,calendar.monthrange(today.year,today.month)[1]))
    if result<today:
        y,m=(today.year+1,1) if today.month==12 else (today.year,today.month+1)
        result=date(y,m,min(day,calendar.monthrange(y,m)[1]))
    return result.isoformat()

def dashboard(start, end, source):
    date.fromisoformat(start); date.fromisoformat(end)
    if start>end or source not in ('codex','api_tracked','api_org'): raise ValueError('Ugyldigt filter')
    with connect() as c:
        rows=[dict(r) for r in c.execute('''SELECT e.*, COALESCE(l.program,e.program) AS display_program,
          COALESCE(l.function,e.function) AS display_function FROM events e LEFT JOIN labels l ON e.task=l.task
          WHERE e.day>=? AND e.day<=? AND e.source=? ORDER BY e.timestamp DESC''',(start,end,source))]
        meta={k:get(c,k) for k in ('limits','collector','api_status','settings','account_usage','credit_purchase')}
    meta['credit_summary']=credit_summary(meta.get('limits') or {},meta.get('credit_purchase') or {})
    if (meta.get('settings') or {}).get('renewal_day'):
        meta['settings']['next_renewal']=next_renewal(meta['settings']['renewal_day'])
    daily={}; programs={}; functions={}; models={}; tasks={}
    total={'input':0,'cached':0,'output':0,'total':0,'requests':len(rows)}
    for r in rows:
        n=r['input']+r['output']
        for k in ('input','cached','output'): total[k]+=r[k]
        total['total']+=n
        daily[r['day']]=daily.get(r['day'],0)+n
        programs[r['display_program']]=programs.get(r['display_program'],0)+n
        models[r['model']]=models.get(r['model'],0)+n
        label=r['display_program']+' / '+r['display_function']
        functions[label]=functions.get(label,0)+n
        t=tasks.setdefault(r['task'],{'id':r['task'],'program':r['display_program'],'function':r['display_function'],
          'day':r['day'],'tokens':0,'model':r['model']})
        t['tokens']+=n
    return {'totals':total,'daily':daily,'programs':programs,'functions':functions,'models':models,
      'tasks':list(tasks.values()),'meta':meta,'server_time':now()}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,status,data,kind='application/json; charset=utf-8'):
        if not isinstance(data,bytes): data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers(); self.wfile.write(data)
    def allowed_host(self):
        host=self.headers.get('Host','')
        return host in ('192.168.1.59:8086','127.0.0.1:8086','localhost:8086')
    def do_GET(self):
        if not self.allowed_host(): return self.send(403,{'error':'Ukendt værtsnavn'})
        u=urlparse(self.path)
        if u.path=='/api/dashboard':
            q=parse_qs(u.query); today=date.today()
            try:
                return self.send(200,dashboard(q.get('start',[(today-timedelta(days=29)).isoformat()])[0],q.get('end',[today.isoformat()])[0],q.get('source',['codex'])[0]))
            except ValueError: return self.send(400,{'error':'Ugyldigt datofilter'})
        files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/favicon.svg':'favicon.svg'}
        if u.path not in files: return self.send(404,{'error':'Ikke fundet'})
        name=files[u.path]; mime={'html':'text/html','js':'text/javascript','css':'text/css','svg':'image/svg+xml'}[name.split('.')[-1]]
        self.send(200,(ROOT/'static'/name).read_bytes(),mime+'; charset=utf-8')
    def do_POST(self):
        # Writes require a same-origin browser request; no CORS or remote ingestion.
        if not self.allowed_host() or self.headers.get('Origin')!='http://'+self.headers.get('Host',''):
            return self.send(403,{'error':'Kun samme oprindelse er tilladt'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<8192: raise ValueError()
            p=json.loads(self.rfile.read(length))
            with connect() as c:
                if self.path=='/api/label':
                    task=str(p['task']); program=str(p['program']).strip(); function=str(p['function']).strip()
                    if not program or not function or max(len(program),len(function))>100: raise ValueError()
                    if not c.execute('SELECT 1 FROM events WHERE task=?',(task,)).fetchone(): raise ValueError()
                    c.execute('INSERT OR REPLACE INTO labels VALUES (?,?,?)',(task,program,function))
                elif self.path=='/api/settings':
                    day=int(p['renewal_day']); price=float(p['monthly_price']); plan=str(p['plan']).strip()
                    if not 1<=day<=31 or not math.isfinite(price) or not 0<=price<=100000 or not 0<len(plan)<=50: raise ValueError()
                    put(c,'settings',{'renewal_day':day,'monthly_price':price,'currency':'USD','plan':plan,'source':'user'})
                else: return self.send(404,{'error':'Ikke fundet'})
            self.send(200,{'ok':True})
        except (ValueError,KeyError,TypeError): self.send(400,{'error':'Kontrollér de indtastede værdier'})

def api_loop():
    from api_sync import sync
    while True:
        try: sync()
        except Exception:
            with connect() as c: put(c,'api_status',{'state':'error','at':now(),'message':'API-opdatering mislykkedes. Kontrollér forbindelsen og din Admin API-nøgle.'})
        time.sleep(900)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--import-data',action='store_true'); args=parser.parse_args()
    if args.import_data:
        print(json.dumps({'imported':import_events(json.load(sys.stdin))})); sys.exit()
    connect().close()
    threading.Thread(target=api_loop,daemon=True).start()
    ThreadingHTTPServer((os.environ.get('FORBRUG_BIND','192.168.1.59'),8086),Handler).serve_forever()
