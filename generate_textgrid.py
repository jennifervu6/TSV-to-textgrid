#!/usr/bin/env python3
"""Generate a Praat TextGrid from a TSV of times (seconds) and optional labels.

Usage examples:
  python generate_textgrid.py input.tsv output.TextGrid
  python generate_textgrid.py input.tsv -o out.TextGrid --mode point --duration 10

Input TSV format (tab-separated):
  time [\t label]
  e.g.:
  0.5\tword1
  1.2\tword2
  2.0

Behavior:
  - By default `--mode auto` will create a TextTier (point tier) if any label is present,
    otherwise an IntervalTier with intervals between times.
  - Use `--mode point` or `--mode interval` to force a mode.
  - If `--duration` is not provided, xmax will be max(time) + 1.0
"""
import argparse
import csv
import sys
from typing import List, Tuple


def write_textgrid_point(times_labels: List[Tuple[float, str]], xmin: float, xmax: float, tier_name: str, out_path: str):
    n = len(times_labels)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("File type = \"ooTextFile\"\n")
        f.write("Object class = \"TextGrid\"\n\n")
        f.write(f"xmin = {xmin}\n")
        f.write(f"xmax = {xmax}\n")
        f.write("tiers? <exists>\n")
        f.write("size = 1\n")
        f.write("item []:\n")
        f.write("    item [1]:\n")
        f.write("        class = \"TextTier\"\n")
        f.write(f"        name = \"{tier_name}\"\n")
        f.write(f"        xmin = {xmin}\n")
        f.write(f"        xmax = {xmax}\n")
        f.write(f"        points: size = {n}\n")
        for i, (t, label) in enumerate(times_labels, start=1):
            f.write(f"        points [{i}]:\n")
            f.write(f"            number = {t}\n")
            f.write(f"            mark = \"{label.replace('\\', '\\\\').replace('\"', '\\"')}\"\n")


def write_textgrid_interval(boundaries: List[float], labels: List[str], xmin: float, xmax: float, tier_name: str, out_path: str):
    # boundaries: sorted list of boundary times, e.g. [t0, t1, t2, ...]
    # intervals: [ (boundaries[0], boundaries[1]), (boundaries[1], boundaries[2]), ... ]
    intervals = []
    if len(boundaries) == 0:
        intervals = [(xmin, xmax, "")]
    else:
        # Pre-interval from xmin to first boundary if xmin < first boundary
        if xmin < boundaries[0]:
            intervals.append((xmin, boundaries[0], ""))
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            label = labels[i] if i < len(labels) else ""
            intervals.append((start, end, label))
        # last interval from last boundary to xmax
        last = boundaries[-1]
        if last < xmax:
            last_label = labels[len(boundaries)-1] if len(labels) >= len(boundaries) else ""
            intervals.append((last, xmax, last_label))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("File type = \"ooTextFile\"\n")
        f.write("Object class = \"TextGrid\"\n\n")
        f.write(f"xmin = {xmin}\n")
        f.write(f"xmax = {xmax}\n")
        f.write("tiers? <exists>\n")
        f.write("size = 1\n")
        f.write("item []:\n")
        f.write("    item [1]:\n")
        f.write("        class = \"IntervalTier\"\n")
        f.write(f"        name = \"{tier_name}\"\n")
        f.write(f"        xmin = {xmin}\n")
        f.write(f"        xmax = {xmax}\n")
        f.write(f"        intervals: size = {len(intervals)}\n")
        for i, (start, end, label) in enumerate(intervals, start=1):
            f.write(f"        intervals [{i}]:\n")
            f.write(f"            xmin = {start}\n")
            f.write(f"            xmax = {end}\n")
            f.write(f"            text = \"{label.replace('\\', '\\\\').replace('\"', '\\"')}\"\n")


def parse_tsv(path: str, time_col: int = 0, label_col: int = 1, delimiter: str = '\t'):
    times = []
    labels = []
    with open(path, newline='', encoding='utf-8') as tsvfile:
        reader = csv.reader(tsvfile, delimiter=delimiter)
        for row in reader:
            if not row:
                continue
            # Skip rows that are comments
            if row[0].strip().startswith('#'):
                continue
            # try to parse time
            try:
                time_str = row[time_col].strip()
                t = float(time_str)
            except Exception:
                # skip rows with non-numeric time
                continue
            label = ""
            if len(row) > label_col:
                label = row[label_col].strip()
            times.append(t)
            labels.append(label)
    return times, labels


def main():
    parser = argparse.ArgumentParser(description="Generate a Praat TextGrid from a TSV of times and optional labels.")
    parser.add_argument('input', help='Input TSV file (tab-separated by default)')
    parser.add_argument('output', nargs='?', help='Output TextGrid path (default input with .TextGrid)', default=None)
    parser.add_argument('--mode', choices=['auto','point','interval'], default='auto', help='Tier mode: point=TextTier, interval=IntervalTier, auto=pick based on labels')
    parser.add_argument('--duration', type=float, help='Set xmax (seconds). If not set uses max(time)+1.0')
    parser.add_argument('--tier-name', default='events', help='Name of the tier in the TextGrid')
    parser.add_argument('--delimiter', default='\t', help='TSV delimiter (default tab)')
    parser.add_argument('--time-col', type=int, default=0, help='0-based column index for times')
    parser.add_argument('--label-col', type=int, default=1, help='0-based column index for labels')
    parser.add_argument('--tail', type=float, default=1.0, help='When duration not specified, add this to last timestamp for xmax')

    args = parser.parse_args()

    out_path = args.output
    if out_path is None:
        if args.input.lower().endswith('.tsv'):
            out_path = args.input[:-4] + '.TextGrid'
        else:
            out_path = args.input + '.TextGrid'

    times, labels = parse_tsv(args.input, time_col=args.time_col, label_col=args.label_col, delimiter=args.delimiter)
    if len(times) == 0:
        print("No valid time entries found in input.", file=sys.stderr)
        sys.exit(1)

    # sort by time
    combined = sorted(zip(times, labels), key=lambda x: x[0])
    times = [c[0] for c in combined]
    labels = [c[1] for c in combined]

    xmin = 0.0
    if args.duration is not None:
        xmax = args.duration
    else:
        xmax = max(times) + args.tail

    mode = args.mode
    if mode == 'auto':
        any_labels = any(lbl for lbl in labels)
        mode = 'point' if any_labels else 'interval'

    if mode == 'point':
        times_labels = [(t, lbl) for t, lbl in zip(times, labels)]
        write_textgrid_point(times_labels, xmin, xmax, args.tier_name, out_path)
    else:
        # For intervals, boundaries are times; labels assigned to intervals starting at each boundary
        boundaries = times
        write_textgrid_interval(boundaries, labels, xmin, xmax, args.tier_name, out_path)

    print(f"Wrote TextGrid to {out_path}")


if __name__ == '__main__':
    main()
