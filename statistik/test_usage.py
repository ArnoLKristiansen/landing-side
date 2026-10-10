import os, tempfile, unittest, json
from unittest.mock import patch
from io import BytesIO
from pathlib import Path
temp=tempfile.TemporaryDirectory();os.environ['FORBRUG_DATA']=temp.name
from storage import connect, import_events, DATA
from collector import collect
from server import dashboard, next_renewal
from datetime import date
from usage_tracker import record_usage

class UsageTests(unittest.TestCase):
    def test_monthly_renewal(self):
        self.assertEqual(next_renewal(4,date(2026,9,25)),'2026-10-04')
        self.assertEqual(next_renewal(4,date(2026,10,4)),'2026-10-04')
        self.assertEqual(next_renewal(4,date(2026,12,5)),'2027-01-04')
        self.assertEqual(next_renewal(31,date(2027,2,1)),'2027-02-28')
    def setUp(self):
        with connect() as c:
            for table in ('events','labels','meta'):c.execute('DELETE FROM '+table)
    def test_api_dedupe_and_cached_not_added_twice(self):
        r={'id':'response-1','usage':{'input_tokens':100,'output_tokens':20,'input_tokens_details':{'cached_tokens':80}}}
        record_usage(r,'Test','Søg');record_usage(r,'Test','Søg')
        d=dashboard('2000-01-01','2100-01-01','api_tracked')
        self.assertEqual(d['totals']['total'],120);self.assertEqual(d['totals']['cached'],80)
        self.assertEqual(len(d['tasks']),1)
        self.assertEqual(dashboard('2000-01-01','2100-01-01','api_org')['totals']['total'],0)
    def test_legacy_duplicate_and_midnight(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'x.jsonl'
            meta={'type':'session_meta','payload':{'id':'s','cwd':'/project'}}
            def event(ts,n):return {'timestamp':ts,'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':n,'cached_input_tokens':0,'output_tokens':0,'total_tokens':n}}}}
            p.write_text('\n'.join(map(json.dumps,[meta,event('2026-09-25T21:00:00Z',10),event('2026-09-25T21:00:00Z',10),event('2026-09-25T22:01:00Z',25)])))
            got=collect(Path(folder));self.assertEqual([x['input'] for x in got['events']],[10,15]);self.assertEqual([x['day'] for x in got['events']],['2026-09-25','2026-09-26'])
    def test_detailed_records_preferred_and_reimport(self):
        with tempfile.TemporaryDirectory() as folder:
            rows=[{'type':'session_meta','payload':{'id':'s'}},{'timestamp':'2026-09-25T12:00:00Z','type':'token_usage_record','payload':{'response_id':'a','usage':{'input_tokens':9,'output_tokens':1}}},{'timestamp':'2026-09-25T12:00:01Z','type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':9,'output_tokens':1,'total_tokens':10}}}}]
            (Path(folder)/'x.jsonl').write_text('\n'.join(map(json.dumps,rows)))
            payload=collect(Path(folder));import_events(payload);import_events(payload)
            d=dashboard('2026-09-25','2026-09-25','codex');self.assertEqual(d['totals']['total'],10)
            with connect() as c:c.execute('INSERT INTO labels VALUES (?,?,?)',(d['tasks'][0]['id'],'Portal','Banner'))
            self.assertEqual(dashboard('2026-09-25','2026-09-25','codex')['programs'],{'Portal':10})
    def test_invalid_tokens_rejected(self):
        with self.assertRaises(ValueError):record_usage({'id':'x','usage':{'input_tokens':-1}},'A','B')
    def test_api_pages_and_failed_refresh_keeps_existing_data(self):
        import api_sync, time
        (DATA/'openai-admin-key').write_text('sk-test-not-a-real-key')
        def page(n,more=False):
            return BytesIO(json.dumps({'data':[{'start_time':int(time.time()),'results':[{'project_id':str(n),'model':'test','input_tokens':10,'output_tokens':2}]}],'has_more':more,'next_page':'page2' if more else None}).encode())
        try:
            with patch('api_sync.urlopen',side_effect=[page(1,True),page(2),page(3)]) as request:
                api_sync.sync();self.assertIn('page=page2',request.call_args_list[1].args[0].full_url)
            self.assertEqual(dashboard('2000-01-01','2100-01-01','api_org')['totals']['total'],36)
            with patch('api_sync.urlopen',side_effect=[page(9,True),OSError('offline')]):
                with self.assertRaises(OSError):api_sync.sync()
            self.assertEqual(dashboard('2000-01-01','2100-01-01','api_org')['totals']['total'],36)
        finally:(DATA/'openai-admin-key').unlink()
if __name__=='__main__':unittest.main()
