#!/usr/bin/env python3
"""Offline StoreFlow dashboard for observed ROI statistics (not verified customers)."""
from __future__ import annotations
import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from html import escape
import json
import math
from pathlib import Path
import sys

class GateFailure(ValueError):
    pass


def need(ok: bool, message: str) -> None:
    if not ok:
        raise GateFailure(message)


def number(value, label, positive=False) -> float:
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise GateFailure(f"Invalid number {label}: {value!r}") from None
    need(math.isfinite(result) and (result > 0 if positive else result >= 0),
         f"Invalid nonnegative/positive number: {label}")
    return result


def rows(path: Path, required: set[str]):
    need(path.is_file(), f"Missing file: {path}")
    with path.open(encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        need(r.fieldnames is not None and required.issubset(r.fieldnames),
             f"Missing CSV columns in {path.name}: {sorted(required - set(r.fieldnames or []))}")
        return list(r)


def read_inputs(base: Path):
    def file_json(name):
        p = base / name
        need(p.is_file(), f"Missing file: {p}")
        return json.loads(p.read_text(encoding='utf-8'))
    summary = file_json('roi_summary.json')
    validation = file_json('roi_validation_report.json')
    occupancy = rows(base / 'roi_occupancy.csv', {'time_s','frame','zone','observed_ids_in_zone'})
    tracks = rows(base / 'roi_track_summary.csv', {'track_id','zone','observed_frames','observed_s','observed_entries','uncertain_starts'})
    events = rows(base / 'roi_events.csv', {'time_s','zone','event','track_id'})
    return summary, validation, occupancy, tracks, events


def validate(summary, validation, occupancy, tracks, events):
    fps = number(summary.get('fps'), 'fps', positive=True)
    count = number(summary.get('frame_count'), 'frame_count', positive=True)
    need(count.is_integer(), 'frame_count must be integer')
    count = int(count)
    metric = summary.get('zone_metrics')
    need(isinstance(metric, dict) and metric, 'zone_metrics missing or empty')
    names = sorted(metric)
    need(validation.get('status') == 'ALL_COMPUTATION_GATES_PASS', 'Upstream ROI compute gates not all PASS')
    need(all(isinstance(g, dict) and g.get('status') == 'PASS' for g in validation.get('gates', {}).values())
         and len(validation.get('gates', {})) >= 5, 'Upstream gate list incomplete or failed')
    need(len(occupancy) == count * len(names), 'ROI occupancy frame count mismatch')
    observed_by_zone = defaultdict(dict)
    for r in occupancy:
        zone = r['zone']
        need(zone in metric, f'Unknown occupancy zone: {zone}')
        try:
            frame = int(r['frame'])
            persons = int(r['observed_ids_in_zone'])
        except (ValueError, TypeError):
            raise GateFailure('Invalid frame/occupancy integer') from None
        need(0 <= frame < count and persons >= 0, f'Invalid occupancy row {r}')
        need(frame not in observed_by_zone[zone], f'Duplicate frame in zone {zone}: {frame}')
        t = number(r['time_s'], 'time_s')
        need(abs(t - frame / fps) <= .0021, f'Frame timestamp mismatch: {zone} frame {frame}')
        observed_by_zone[zone][frame] = persons
    track_by_zone = defaultdict(list)
    for r in tracks:
        need(r['zone'] in metric, f'Unknown track zone: {r["zone"]}')
        frames = number(r['observed_frames'], 'observed_frames')
        need(frames.is_integer(), 'observed_frames must be integer')
        need(abs(number(r['observed_s'], 'observed_s') - frames/fps) < .002,
             f'Observed seconds mismatch for track {r["track_id"]}')
        number(r['observed_entries'], 'observed_entries')
        number(r['uncertain_starts'], 'uncertain_starts')
        track_by_zone[r['zone']].append(r)
    event_by_zone = defaultdict(Counter)
    for e in events:
        need(e['zone'] in metric, f'Unknown event zone: {e["zone"]}')
        event_by_zone[e['zone']][e['event']] += 1
    for zone in names:
        series = observed_by_zone[zone]
        need(len(series) == count, f'Missing occupancy frames in zone {zone}')
        data = [series[i] for i in range(count)]
        zone_tracks = track_by_zone[zone]
        m = metric[zone]
        total_frames = sum(data)
        need(int(m['observed_track_ids']) == len(zone_tracks), f'{zone}: track count mismatch')
        need(abs(number(m['observed_track_seconds'], 'observed_track_seconds') - total_frames/fps) < .002,
             f'{zone}: track-seconds do not match occupancy')
        need(abs(number(m['average_observed_occupancy'], 'average_observed_occupancy') - total_frames/count) < .002,
             f'{zone}: average occupancy mismatch')
        need(int(m['peak_observed_occupancy']) == max(data), f'{zone}: peak mismatch')
        need(sum(int(t['observed_frames']) for t in zone_tracks) == total_frames,
             f'{zone}: track observed-frame reconciliation failure')
        need(sum(int(t['observed_entries']) for t in zone_tracks) == int(m['adjacent_frame_enter_events']),
             f'{zone}: entry totals mismatch')
        need(sum(int(t['uncertain_starts']) for t in zone_tracks) == int(m['unconfirmed_segment_starts']),
             f'{zone}: uncertain-start totals mismatch')
        ev = event_by_zone[zone]
        need(ev['OBSERVED_ENTER_ZONE'] == int(m['adjacent_frame_enter_events']),
             f'{zone}: event CSV entry totals mismatch')
        need(ev['FIRST_OBSERVED_IN_ZONE'] + ev['REAPPEARED_IN_ZONE'] == int(m['unconfirmed_segment_starts']),
             f'{zone}: event CSV uncertain totals mismatch')
    return {"fps": fps, "frames": count, "zones": names, "series": observed_by_zone}


def chart_svg(series: dict[int,int], fps: float, frames: int, width=900, height=185):
    # 1-second bin averages; no interpolated observations
    bins = defaultdict(list)
    for frame in range(frames):
        bins[int(frame / fps)].append(series[frame])
    means = [sum(v)/len(v) for _,v in sorted(bins.items())]
    if not means:
        means = [0]
    ymax = max(1, max(means))
    pad_x, pad_y = 38, 23
    drawable_w, drawable_h = width - 2*pad_x, height - 2*pad_y
    points = []
    for i, value in enumerate(means):
        x = pad_x + (i/max(1,len(means)-1))*drawable_w
        y = pad_y + drawable_h - (value/ymax)*drawable_h
        points.append(f'{x:.1f},{y:.1f}')
    grids = ''.join(f'<line x1="{pad_x}" x2="{width-pad_x}" y1="{pad_y+drawable_h*j/4:.1f}" y2="{pad_y+drawable_h*j/4:.1f}" stroke="#dce7ea" stroke-dasharray="3 5"/>' for j in range(5))
    labels = f'<text x="{pad_x}" y="{height-2}" fill="#637884" font-size="12">0초</text><text x="{width-pad_x}" y="{height-2}" text-anchor="end" fill="#637884" font-size="12">{frames/fps:.1f}초</text>'
    return f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="초 단위 구역 관측 인원 평균 변화">{grids}<polyline points="{" ".join(points)}" fill="none" stroke="#007b89" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>{labels}</svg>'


def fmt(value, decimals=2):
    return f'{float(value):,.{decimals}f}'


def make_html(summary, validation, occupancy, tracks, events, state):
    zone_names = state['zones']
    duration = float(summary['frame_count']) / float(summary['fps'])
    summary_cards = []
    sections = []
    for zone in zone_names:
        m = summary['zone_metrics'][zone]
        name = escape(zone)
        summary_cards.append(f'''<section class="tile"><div class="muted">{name} · 관측 ID</div><div class="kpi">{int(m['observed_track_ids'])}</div><div class="detail">고유 고객 수가 아닌 추적 ID 수</div></section>''')
        summary_cards.append(f'''<section class="tile"><div class="muted">{name} · 누적 관측량</div><div class="kpi">{fmt(m['observed_track_seconds'], 2)}<small> ID·초</small></div><div class="detail">구역 내 ID 관측 프레임 / FPS</div></section>''')
        summary_cards.append(f'''<section class="tile"><div class="muted">{name} · 평균 관측 인원</div><div class="kpi">{fmt(m['average_observed_occupancy'], 3)}</div><div class="detail">프레임 평균, 실제 고객 수 아님</div></section>''')
        summary_cards.append(f'''<section class="tile"><div class="muted">{name} · 최고 동시 관측</div><div class="kpi">{int(m['peak_observed_occupancy'])}</div><div class="detail">{fmt(m['peak_frame_time_s'], 1)}초 부근 · 오탐 가능</div></section>''')
        charts = chart_svg(state['series'][zone], state['fps'], state['frames'])
        track_zone = sorted([x for x in tracks if x['zone'] == zone], key=lambda x:-float(x['observed_s']))[:8]
        bodies = ''.join(f'<tr><td>{escape(str(t["track_id"]))}</td><td>{fmt(t["observed_s"],3)}</td><td>{escape(str(t["observed_entries"]))}</td><td>{escape(str(t["uncertain_starts"]))}</td></tr>' for t in track_zone)
        sections.append(f'''<section class="panel"><h2>{name} · 초 단위 관측 인원 변화</h2><p class="muted">1초 구간 내 프레임 평균. 사람을 추정하지 않고 감지된 ID만 세어 표시합니다.</p>{charts}</section>
        <section class="panel"><h2>{name} · 이벤트 신뢰성</h2><div class="kpirow"><div><strong>{int(m['adjacent_frame_enter_events'])}</strong><span>연속 관측으로 확인된 구역 진입</span></div><div><strong>{int(m['unconfirmed_segment_starts'])}</strong><span>진입 불확실 구간 시작</span></div></div><p class="muted">두 수치 모두 실제 신규 고객 수를 의미하지 않습니다.</p></section>
        <section class="panel"><h2>{name} · 관측시간 상위 추적 ID</h2><table><thead><tr><th>추적 ID</th><th>관측 초</th><th>확인 진입</th><th>불확실 시작</th></tr></thead><tbody>{bodies}</tbody></table></section>''')
    total_uncertain = sum(int(summary['zone_metrics'][z]['unconfirmed_segment_starts']) for z in zone_names)
    total_entry = sum(int(summary['zone_metrics'][z]['adjacent_frame_enter_events']) for z in zone_names)
    quality = escape(validation.get('quality_status', 'UNKNOWN'))
    hypotheses = [
        'ROI가 실제 키오스크 앞 바닥 영역과 일치하는지 영상으로 다시 검토',
        '수작업으로 표시한 고객과 추적 ID를 비교해 누락·재식별 문제 확인',
        '비즈니스 가설: 충분한 길이와 정확도의 데이터가 확보되면 키오스크 주변 혼잡·체류 변화로 동선 재배치 시험',
    ]
    if total_uncertain > total_entry:
        hypotheses.insert(0, '불확실한 관측 시작이 확인된 구역 진입보다 많으므로 탐지·추적 안정성 개선을 우선')
    recommendations = ''.join(f'<li>{escape(x)}</li>' for x in hypotheses)
    limitations = ''.join(f'<li>{escape(str(x))}</li>' for x in summary.get('limitations', []))
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>StoreFlow · ROI Insights</title><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#f3f7f7;color:#162f39;font:15px/1.65 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}}main{{max-width:1080px;margin:auto;padding:34px 22px 70px}}h1{{font-size:34px;margin:0 0 4px;letter-spacing:-1px}}h2{{font-size:20px;margin:0 0 7px}}.eyebrow{{font-size:12px;letter-spacing:1.6px;font-weight:800;color:#087481}}.muted{{color:#60747e}}.top{{display:flex;justify-content:space-between;gap:15px;align-items:center;flex-wrap:wrap}}.pill{{border:1px solid #b26d1b;color:#854b0d;background:#fff8e9;padding:7px 12px;border-radius:999px;font-weight:700;font-size:12px}}.warning{{background:#fff5e1;border-left:4px solid #cd9228;padding:16px 19px;border-radius:8px;margin:22px 0}}.cards{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:22px 0}}.tile,.panel{{background:#fff;border:1px solid #e0e9ea;border-radius:15px;padding:19px;box-shadow:0 3px 13px #113b440b}}.kpi{{font-size:30px;letter-spacing:-1px;font-weight:800;line-height:1.35}}.kpi small{{font-size:15px;font-weight:600}}.detail{{font-size:12px;color:#70838d}}.panel{{margin:14px 0}}.panel svg{{width:100%;max-height:220px}}.kpirow{{display:flex;gap:35px;flex-wrap:wrap}}.kpirow>div{{display:flex;flex-direction:column}}.kpirow strong{{font-size:29px}}.kpirow span{{font-size:12px;color:#66808a}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:8px;text-align:left;border-bottom:1px solid #e7eef0}}th{{color:#526e76;font-weight:600}}ol,ul{{padding-left:23px;margin:10px 0}}footer{{color:#71848b;font-size:12px;margin-top:30px}}@media(max-width:850px){{.cards{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:500px){{.cards{{grid-template-columns:1fr 1fr}}.tile{{padding:12px}}.kpi{{font-size:23px}}}}
    </style></head><body><main><div class="top"><div><div class="eyebrow">STOREFLOW / OFFLINE INSIGHTS</div><h1>키오스크 주변 관측 분석</h1><p class="muted">영상 길이 {fmt(duration,1)}초 · {state['frames']}프레임 · {fmt(state['fps'],1)} FPS</p></div><div class="pill">실험 결과 · {quality}</div></div>
    <div class="warning"><strong>이 자료는 매장 운영 판단용 데이터가 아닙니다.</strong><div>기존 YOLO 예비 탐지 F1이 낮고 ID 재생성이 있을 수 있습니다. 아래의 인원·관측시간은 실제 고객 수·주문 대기시간·매출을 뜻하지 않습니다.</div></div>
    <div class="cards">{''.join(summary_cards)}</div>{''.join(sections)}
    <section class="panel"><h2>현재 결과로 도출 가능한 개선 가설</h2><ol>{recommendations}</ol></section>
    <section class="panel"><h2>분석 한계 · 데이터 해석</h2><ul>{limitations}</ul><p class="muted">계산 검증: ALL_COMPUTATION_GATES_PASS. 탐지·추적 정확도: 미검증. 확인된 구역 진입 {total_entry}건 / 불확실 구간 시작 {total_uncertain}건.</p></section><footer>StoreFlow ROI Add-on · 로컬 CSV/JSON에서 생성된 정적 대시보드. 외부 서버로 영상이나 로그를 전송하지 않습니다.</footer></main></body></html>'''


def run(base: Path, out: Path):
    summary, validation, occupancy, tracks, events = read_inputs(base)
    state = validate(summary, validation, occupancy, tracks, events)
    page = make_html(summary, validation, occupancy, tracks, events, state)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding='utf-8')
    print('[PASS] D1 input + D2 accounting + D3 reporting')
    print('[QUALITY]', validation.get('quality_status', 'UNKNOWN'))
    print('[DASHBOARD]', out)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description='Create a local, evidence-labeled StoreFlow business dashboard')
    p.add_argument('--base', type=Path, default=Path('outputs/quality_run/roi_insights'))
    p.add_argument('--out', type=Path, default=Path('outputs/quality_run/business_dashboard/index.html'))
    args = p.parse_args(argv)
    try:
        run(args.base, args.out)
    except (GateFailure, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f'[FAIL] {type(exc).__name__}: {exc}', file=sys.stderr)
        print('[NEXT] Check source ROI CSV/JSON and rerun the failed pipeline stage; dashboard not created.', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
