import argparse
import csv
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

import cv2
import numpy as np

from storeflow_roi import (Zone, Observation, RectSetup, analyze, assert_accounting,
                           compute, config_from_path, read_observations,
                           validate_zones, video_metadata, zone_for)


def meta(fps=10., frame_count=20, width=100, height=80):
    return dict(fps=fps, frame_count=frame_count, width=width, height=height)


Z = [Zone("KIOSK", .2, .2, .6, .8)]


class ROIUnitTests(unittest.TestCase):
    def test_inside_outside_and_edge(self):
        self.assertEqual(zone_for(20, 20, 100, 100, Z), "KIOSK")
        self.assertEqual(zone_for(60, 20, 100, 100, Z), None)
        self.assertEqual(zone_for(50, 80, 100, 100, Z), None)

    def test_invalid_empty_zones(self):
        with self.assertRaises(ValueError): validate_zones([])

    def test_duplicate_zone_name(self):
        with self.assertRaises(ValueError): validate_zones(Z + Z)

    def test_inverted_zone(self):
        with self.assertRaises(ValueError): validate_zones([Zone("X", .7, .1, .2, .5)])

    def test_out_of_range_zone(self):
        with self.assertRaises(ValueError): validate_zones([Zone("X", .1, .2, 1.2, .7)])

    def test_nonfinite_zone(self):
        with self.assertRaises(ValueError): validate_zones([Zone("X", float("nan"), .2, .5, .9)])

    def test_overlapping_zones_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_zones([Zone("A",.1,.1,.6,.6), Zone("B",.5,.5,.9,.9)])

    def test_adjacent_zones_allowed(self):
        validate_zones([Zone("A",0,0,.5,1), Zone("B",.5,0,1,1)])

    def test_direct_zone_transition(self):
        obs=[Observation(0,0,1,10,40),Observation(1,.1,1,30,40),Observation(2,.2,1,32,40),Observation(3,.3,1,90,40)]
        res=compute(obs,Z,meta())
        events=[e["event"] for e in res["events"]]
        self.assertIn("OBSERVED_ENTER_ZONE",events)
        self.assertIn("OBSERVED_LEAVE_ZONE",events)
        self.assertEqual(res["tracks"][0]["observed_frames"],2)
        self.assertEqual(res["tracks"][0]["observed_s"], .2)
        self.assertEqual(res["tracks"][0]["observed_entries"],1)

    def test_no_interpolation_through_gap(self):
        obs=[Observation(0,0,3,30,40),Observation(1,.1,3,31,40),Observation(7,.7,3,32,40)]
        res=compute(obs,Z,meta())
        self.assertEqual(res["tracks"][0]["observed_s"], .3)
        self.assertEqual(res["tracks"][0]["segments"],2)
        self.assertEqual(res["tracks"][0]["observed_entries"],0)
        self.assertEqual(res["tracks"][0]["uncertain_starts"],2)
        events=[e["event"] for e in res["events"]]
        self.assertIn("OBSERVATION_INTERRUPTED",events)
        self.assertIn("REAPPEARED_IN_ZONE",events)
        self.assertNotIn("OBSERVED_LEAVE_ZONE",events)
        assert_accounting(res,obs,Z,meta())

    def test_end_does_not_claim_exit(self):
        obs=[Observation(0,0,3,30,40)]
        e=[x["event"] for x in compute(obs,Z,meta())["events"]]
        self.assertIn("LAST_OBSERVED_IN_ZONE",e)
        self.assertNotIn("OBSERVED_LEAVE_ZONE",e)

    def test_gap_to_outside_not_exit(self):
        obs=[Observation(0,0,3,30,40),Observation(3,.3,3,90,40)]
        e=[x["event"] for x in compute(obs,Z,meta())["events"]]
        self.assertIn("OBSERVATION_INTERRUPTED",e)
        self.assertNotIn("OBSERVED_LEAVE_ZONE",e)

    def test_missing_everything_returns_zero(self):
        res=compute([Observation(0,0,3,90,40)],Z,meta())
        self.assertEqual(res["tracks"],[])
        self.assertEqual(res["aggregate"]["KIOSK"]["peak_observed_occupancy"],0)
        self.assertEqual(len(res["occupancy"]),20)

    def test_concurrent_occupancy(self):
        obs=[Observation(1,.1,1,30,40),Observation(1,.1,2,35,45),Observation(2,.2,1,30,40)]
        res=compute(obs,Z,meta())
        self.assertEqual(res["aggregate"]["KIOSK"]["peak_observed_occupancy"],2)
        self.assertEqual(res["aggregate"]["KIOSK"]["observed_track_seconds"],.3)
        assert_accounting(res,obs,Z,meta())

    def test_accounting_detects_tampering(self):
        obs=[Observation(1,.1,1,30,40)]
        res=compute(obs,Z,meta())
        res["tracks"][0]["observed_frames"] = 9
        with self.assertRaisesRegex(ValueError,"Track observed seconds mismatch"):
            assert_accounting(res,obs,Z,meta())
        res["tracks"][0]["observed_s"] = .9
        with self.assertRaisesRegex(ValueError,"ACCOUNTING FAIL"):
            assert_accounting(res,obs,Z,meta())


class ROIFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root/"test.mp4"
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (100,80))
        self.assertTrue(writer.isOpened())
        for i in range(20):
            frame=np.full((80,100,3),90,dtype=np.uint8)
            cv2.circle(frame,(30 + i//3,45),5,(255,255,255),-1)
            writer.write(frame)
        writer.release()
        self.csv = self.root/"tracks.csv"
        self.config=self.root/"roi.json"
        self.config.write_text(json.dumps({"version":1,"width":100,"height":80,"zones":[Z[0].__dict__]}), encoding="utf-8")
        self.out=self.root/"out"

    def create_csv(self, rows):
        with self.csv.open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.DictWriter(f, fieldnames=["time_s","track_id","foot_x","foot_y","zone","direction","elapsed_s","zone_elapsed_s"])
            w.writeheader()
            w.writerows(rows)

    def row(self, t=0.,tid=3,x=30,y=40):
        return dict(time_s=f"{t:.3f}",track_id=tid,foot_x=x,foot_y=y,zone="CENTER",direction="STILL",elapsed_s="0.100",zone_elapsed_s="0.100")

    def test_metadata(self):
        m=video_metadata(self.video)
        self.assertEqual(m["width"],100)
        self.assertEqual(m["height"],80)
        self.assertEqual(m["frame_count"],20)

    def test_missing_csv(self):
        with self.assertRaises(FileNotFoundError):read_observations(self.csv,meta())

    def test_missing_columns(self):
        self.csv.write_text("time_s,track_id\n0,3\n",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Required CSV"):
            read_observations(self.csv,meta())

    def test_duplicate_track_frame(self):
        self.create_csv([self.row(),self.row()])
        with self.assertRaisesRegex(ValueError,"twice"):
            read_observations(self.csv,meta())

    def test_bad_fps_timestamp(self):
        self.create_csv([self.row(t=.055)])
        with self.assertRaisesRegex(ValueError,"inconsistent"):
            read_observations(self.csv,meta())

    def test_bad_coordinates(self):
        self.create_csv([self.row(x=110)])
        with self.assertRaisesRegex(ValueError,"outside"):
            read_observations(self.csv,meta())

    def test_nan_timestamp(self):
        self.create_csv([dict(self.row(),time_s="nan")])
        with self.assertRaisesRegex(ValueError,"nonnegative"):
            read_observations(self.csv,meta())

    def test_timestamp_beyond_video(self):
        self.create_csv([self.row(t=12.)])
        with self.assertRaisesRegex(ValueError,"frame range"):
            read_observations(self.csv,meta())

    def test_resolution_mismatch(self):
        self.config.write_text(json.dumps({"version":1,"width":896,"height":672,"zones":[Z[0].__dict__]}),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"resolution"):
            config_from_path(self.config,meta())

    def test_config_overlaps(self):
        self.config.write_text(json.dumps({"version":1,"width":100,"height":80,"zones":[Z[0].__dict__,Zone("B",.4,.4,.7,.9).__dict__]}),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"overlap"):
            config_from_path(self.config,meta())

    def args(self, no_video=True):
        return SimpleNamespace(video=str(self.video),input_csv=str(self.csv),config=str(self.config),
                               out=str(self.out),no_video=no_video)

    def test_gate_failure_stops_after_r1(self):
        with self.assertRaises(SystemExit): analyze(self.args())
        report=json.loads((self.out/"roi_validation_report.json").read_text())
        self.assertEqual(report["gates"]["R1_VIDEO_AND_CSV"]["status"],"FAIL")
        self.assertEqual(report["gates"]["R2_ROI_CONFIG"]["status"],"NOT_RUN")

    def test_full_integration_csv(self):
        self.create_csv([self.row(t=0),self.row(t=.1),self.row(t=.4),self.row(t=.5,x=90)])
        analyze(self.args())
        result=json.loads((self.out/"roi_summary.json").read_text())
        self.assertEqual(result["zone_metrics"]["KIOSK"]["observed_track_seconds"], .3)
        self.assertEqual(result["zone_metrics"]["KIOSK"]["peak_observed_occupancy"], 1)
        self.assertTrue((self.out/"roi_events.csv").exists())
        report=json.loads((self.out/"roi_validation_report.json").read_text())
        self.assertEqual(report["status"],"ALL_COMPUTATION_GATES_PASS")
        with (self.out/"roi_occupancy.csv").open(encoding="utf-8-sig",newline="") as f:
            self.assertEqual(len(list(csv.DictReader(f))),20)

    def test_full_integration_video(self):
        self.create_csv([self.row(t=0),self.row(t=.1)])
        analyze(self.args(no_video=False))
        p=self.out/"roi_preview.mp4"
        self.assertTrue(p.is_file())
        cap=cv2.VideoCapture(str(p))
        self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),20)
        cap.release()

    def test_setup_draft_mouse_save(self):
        frame=np.zeros((80,100,3),dtype=np.uint8)
        ui=RectSetup(frame,["KIOSK"],self.config,meta(),.5)
        ui.on_mouse(cv2.EVENT_LBUTTONDOWN,30,20,None,None)
        ui.on_mouse(cv2.EVENT_LBUTTONUP,60,60,None,None)
        self.assertTrue(ui.draft_path.is_file())
        ui._click_button("SAVE")
        self.assertTrue(ui.done)
        z=config_from_path(self.config,meta())[0]
        self.assertAlmostEqual(z.x1,.3)
        self.assertAlmostEqual(z.x2,.6)

    def test_setup_save_rejects_overlap(self):
        frame=np.zeros((80,100,3),dtype=np.uint8)
        ui=RectSetup(frame,["A","B"],self.config,meta(),.5)
        ui.rects=[(10,10,70,50),(30,20,90,70)]
        ui._click_button("SAVE")
        self.assertFalse(ui.done)
        self.assertIn("overlap",ui.note)


if __name__ == "__main__": unittest.main()
