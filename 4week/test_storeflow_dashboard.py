import csv
import json
from pathlib import Path
import tempfile
import unittest
from storeflow_dashboard import validate, GateFailure, chart_svg, run, make_html


def fixture():
    m = {'observed_track_ids':1, 'observed_track_seconds':.2, 'average_observed_occupancy':.2,
         'peak_observed_occupancy':1, 'peak_frame_time_s':.0, 'adjacent_frame_enter_events':1,
         'unconfirmed_segment_starts':1}
    s = {'fps':10, 'frame_count':10, 'zone_metrics':{'KIOSK_AREA':m}, 'limitations':['test only']}
    v = {'status':'ALL_COMPUTATION_GATES_PASS','quality_status':'EXPERIMENTAL_NOT_VALIDATED',
         'gates':{f'R{i}':{'status':'PASS'} for i in range(1,6)}}
    occ=[{'frame':i,'time_s':f'{i/10:.3f}','zone':'KIOSK_AREA','observed_ids_in_zone':str(int(i in (1,2)))} for i in range(10)]
    tracks=[{'track_id':'77','zone':'KIOSK_AREA','observed_frames':'2','observed_s':'0.2','observed_entries':'1','uncertain_starts':'1'}]
    events=[{'track_id':'77','zone':'KIOSK_AREA','time_s':'.1','event':'OBSERVED_ENTER_ZONE'},
            {'track_id':'77','zone':'KIOSK_AREA','time_s':'.2','event':'FIRST_OBSERVED_IN_ZONE'}]
    return s,v,occ,tracks,events

class DashboardTests(unittest.TestCase):
    def test_baseline_valid(self):
        s,v,o,t,e=fixture()
        x=validate(s,v,o,t,e)
        self.assertEqual(x['frames'], 10)
    def test_unknown_zone_fails(self):
        s,v,o,t,e=fixture();o[0]['zone']='FAKE'
        with self.assertRaises(GateFailure):validate(s,v,o,t,e)
    def test_bad_accounting_fails(self):
        s,v,o,t,e=fixture();s['zone_metrics']['KIOSK_AREA']['observed_track_seconds']=100
        with self.assertRaises(GateFailure):validate(s,v,o,t,e)
    def test_bad_average_fails(self):
        s,v,o,t,e=fixture();s['zone_metrics']['KIOSK_AREA']['average_observed_occupancy']=.9
        with self.assertRaises(GateFailure):validate(s,v,o,t,e)
    def test_bad_peak_fails(self):
        s,v,o,t,e=fixture();s['zone_metrics']['KIOSK_AREA']['peak_observed_occupancy']=2
        with self.assertRaises(GateFailure):validate(s,v,o,t,e)
    def test_duplicate_frame_fails(self):
        s,v,o,t,e=fixture();o[1]['frame']=0;o[1]['time_s']='0.0'
        with self.assertRaises(GateFailure):validate(s,v,o,t,e)
    def test_event_mismatch_fails(self):
        s,v,o,t,e=fixture();e=[]
        with self.assertRaises(GateFailure):validate(s,v,o,t,e)
    def test_upstream_failed(self):
        s,v,o,t,e=fixture();v['gates']['R2']['status']='FAIL'
        with self.assertRaises(GateFailure):validate(s,v,o,t,e)
    def test_html_sanitization(self):
        s,v,o,t,e=fixture()
        s['limitations']=['<script>alert(1)</script>']
        result=make_html(s,v,o,t,e,validate(s,v,o,t,e))
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;',result)
        self.assertIn('실험 결과',result)
    def test_chart_without_interpolation(self):
        result=chart_svg({i:(1 if i==1 else 0) for i in range(10)},10,10)
        self.assertIn('<polyline',result)
    def test_end_to_end_offline(self):
        s,v,o,t,e=fixture()
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)/'roi'
            base.mkdir()
            (base/'roi_summary.json').write_text(json.dumps(s),encoding='utf-8')
            (base/'roi_validation_report.json').write_text(json.dumps(v),encoding='utf-8')
            for name,rows in [('roi_occupancy.csv',o),('roi_track_summary.csv',t),('roi_events.csv',e)]:
                with (base/name).open('w',newline='',encoding='utf-8') as f:
                    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            out=Path(temp)/'dashboard.html'
            run(base,out)
            self.assertIn('KIOSK_AREA',out.read_text(encoding='utf-8'))
            self.assertIn('미검증',out.read_text(encoding='utf-8'))

if __name__=='__main__':
    unittest.main()
