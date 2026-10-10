"""Mac collector: allowlisted counters only; SSH is the only transport to the server."""
import argparse, hashlib, json, os, select, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

def normalized_limits(raw, ts):
    windows=[]
    for k in ('primary','secondary'):
        w=raw.get(k)
        if w:
            windows.append({'name':k,'used':w.get('usedPercent',w.get('used_percent')),
              'minutes':w.get('windowDurationMins',w.get('window_minutes')),'resets_at':w.get('resetsAt',w.get('resets_at'))})
    cr=raw.get('credits') or {}
    return {'observed_at':ts,'windows':windows,'plan':raw.get('planType',raw.get('plan_type')),
      'credits':cr.get('balance'),'credits_unlimited':cr.get('unlimited',False)}

def collect(root):
    events={}; limits=None; files=0
    for file in sorted(root.rglob('*.jsonl')):
        records=[]; thread=''; cwd=''; turn=''; model='Ukendt model'; legacy=[]; detailed=False; totals=None; task_number=0
        try:
            for line in file.read_text(errors="replace").splitlines():
                try:r=json.loads(line)
                except (ValueError,UnicodeError):continue
                p=r.get('payload') or {}; kind=r.get('type'); ts=r.get('timestamp')
                if not isinstance(p,dict):continue
                if kind=='session_meta':thread=p.get('id','');cwd=p.get('cwd','')
                if kind=='turn_context':
                    newturn=p.get('turn_id','')
                    if newturn!=turn:task_number+=1
                    turn=newturn; model=p.get('model',model);cwd=p.get('cwd',cwd)
                if kind=='token_usage_record':
                    detailed=True
                    records.append((ts,p.get('response_id') or f'{thread}:{r.get("ordinal",ts)}',p.get('turn_id') or turn,p.get('usage',{}),model,cwd,task_number))
                if kind=='event_msg' and p.get('type')=='token_count':
                    raw=p.get('rate_limits')
                    if raw and (not limits or ts>limits['observed_at']):limits=normalized_limits(raw,ts)
                    total=(p.get('info') or {}).get('total_token_usage')
                    if not total:continue
                    keys=('input_tokens','cached_input_tokens','output_tokens')
                    # Account for cumulative totals; repeated token_count notices contribute nothing.
                    usage={k:max(0,total.get(k,0)-(totals or {}).get(k,0)) for k in keys}
                    if totals and total.get('total_tokens',0)<totals.get('total_tokens',0):
                        usage={k:total.get(k,0) for k in keys}
                    totals=total
                    if usage['input_tokens']+usage['output_tokens']:
                        legacy.append((ts,f'{thread}:{ts}:{total.get("total_tokens")}',turn,usage,model,cwd,task_number))
            if not thread:continue
            files+=1
            task_names={}
            for ts,rid,tid,u,model,cwd,num in records if detailed else legacy:
                try:dt=datetime.fromisoformat(ts.replace('Z','+00:00'))
                except (ValueError,AttributeError):continue
                program=Path(cwd).name if '/Documents/Codex/' not in cwd else 'Codex · uden projekt'
                task_names.setdefault(tid, f'Opgave {num or 1} · {dt.astimezone(ZoneInfo("Europe/Copenhagen")).strftime("%d/%m %H:%M")}')
                events[rid]={'id':'codex:'+hashlib.sha256(rid.encode()).hexdigest(),'source':'codex','timestamp':ts,
                  'day':dt.astimezone(ZoneInfo('Europe/Copenhagen')).date().isoformat(),
                  'task':'codex:'+thread+':'+(tid or 'legacy'),'program':program or 'Ukendt projekt',
                  'function':task_names[tid],
                  'model':model,'input':u.get('input_tokens',0),'cached':u.get('cached_input_tokens',0),'output':u.get('output_tokens',0)}
        except OSError:continue
    return {'events':list(events.values()),'limits':limits,'collector':{'files':files,'scope':'Lokale Codex-sessioner på Arnos Mac','limits_source':'Seneste Codex-session'}}

def live_account():
    binary='/Applications/ChatGPT.app/Contents/Resources/codex'
    p=subprocess.Popen([binary,'app-server','proxy'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    buffer=b''
    def send(obj):p.stdin.write(json.dumps(obj).encode()+b'\n');p.stdin.flush()
    def rpc(i,method,params=None):
        nonlocal buffer
        obj={'id':i,'method':method}
        if params is not None:obj['params']=params
        send(obj);until=time.monotonic()+12
        while time.monotonic()<until:
            if b'\n' not in buffer:
                if not select.select([p.stdout],[],[],1)[0]:continue
                chunk=os.read(p.stdout.fileno(),65536)
                if not chunk:raise RuntimeError('App server lukket')
                buffer+=chunk
            while b'\n' in buffer:
                line,buffer=buffer.split(b'\n',1)
                try:r=json.loads(line)
                except ValueError:continue
                if r.get('id')==i:
                    if 'error' in r:raise RuntimeError('App server kunne ikke levere statistik')
                    return r['result']
        raise TimeoutError()
    try:
        rpc(1,'initialize',{'clientInfo':{'name':'alkdata_usage','version':'1.0.0'}})
        send({'method':'initialized'})
        r=rpc(2,'account/rateLimits/read')
        raw=(r.get('rateLimitsByLimitId') or {}).get('codex') or r.get('rateLimits')
        limits=normalized_limits(raw,datetime.now(timezone.utc).isoformat()) if raw else None
        account=None
        try:
            r=rpc(3,'account/usage/read')
            # Only the numeric daily counters are transferred.
            buckets=r.get('dailyUsageBuckets')
            if isinstance(buckets,list):account={'observed_at':datetime.now(timezone.utc).isoformat(),'daily':[
                {'day':b['startDate'],'tokens':b['tokens']} for b in buckets if isinstance(b.get('tokens'),(int,float))]}
        except Exception:pass
        return limits,account
    finally:
        p.terminate()
        try:p.wait(timeout=3)
        except subprocess.TimeoutExpired:p.kill();p.wait()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output');parser.add_argument('--no-live',action='store_true');args=parser.parse_args()
    payload=collect(Path.home()/'.codex/sessions')
    # Archived sessions can contain additional history. Stable response IDs deduplicate them.
    archived=Path.home()/'.codex/archived_sessions'
    if archived.exists():
        other=collect(archived); payload['events']=list({e['id']:e for e in payload['events']+other['events']}.values())
        payload['collector']['files']+=other['collector']['files']
    if not args.no_live:
        try:
            limits,account=live_account()
            if limits:payload['limits']=limits;payload['collector']['limits_source']='OpenAI kontogrænser'
            if account:payload['account_usage']=account
        except Exception:pass
    data=json.dumps(payload).encode()
    if args.output:Path(args.output).write_bytes(data)
    else:
        r=subprocess.run(['/usr/bin/ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','arno@192.168.1.59',
          'cd /home/arno/openai-forbrug && python3 server.py --import-data'],input=data,capture_output=True,timeout=50)
        if r.returncode:raise SystemExit('Synkronisering mislykkedes; prøver igen ved næste kørsel.')
        print(datetime.now().isoformat(),len(payload['events']),'målinger synkroniseret')
if __name__=='__main__':main()
