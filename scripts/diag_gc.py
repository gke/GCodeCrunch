#!/usr/bin/env python3
"""Diagnostic: compare original inter-segment travel with greedy NN travel."""
import sys
import gc_engine as g

path = sys.argv[1] if len(sys.argv) > 1 else \
    "Aircraft/Planks/Gruel/Gruel EMX07/GCODE/LR Gruel VI.gcode"

with open(path, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

chunks = g.split_layers(lines)
state = g.State()
state.abs_e = g.detect_settings(lines, dict(g.DEFAULTS))

orig_total = nn_total = 0.0
nseg_total = 0
worst = []

for idx, chunk in enumerate(chunks):
    if idx == 0:
        g.replay_lines(chunk, state)
        continue
    ps = state.clone()
    pro, segs, trailing = g.extract_layer(chunk, ps)
    if len(segs) < 2:
        g.replay_lines(chunk, state)
        continue

    prev = (state.x, state.y)
    orig = 0.0
    for s in segs:
        orig += g.math.hypot(prev[0] - s.start[0], prev[1] - s.start[1])
        prev = (s.end[0], s.end[1])
    ordered, endp, nn = g.order_segments(segs, (state.x, state.y, state.z), True)

    orig_total += orig
    nn_total += nn
    nseg_total += len(segs)
    worst.append((nn - orig, idx, len(segs), orig, nn))

    g.replay_lines(chunk, state)

print("layers reordered :", len(worst))
print("total segments   :", nseg_total)
print("original travel  : %12.1f mm" % orig_total)
print("greedy NN travel : %12.1f mm" % nn_total)

worst.sort(reverse=True)
print("\nworst layers (nn-orig, chunk_idx, nseg, orig, nn):")
for w in worst[:10]:
    print("  %10.1f  layer#%-4d n=%-5d orig=%9.1f nn=%9.1f" % (w[0], w[1], w[2], w[3], w[4]))

ssegs = sorted(segs, key=len)
print("\nsample first 5 segments of last processed layer (start->end, len):")
big = worst[0][1]
ps = None
# re-extract the worst layer with correct state is complex; just show a generic layer
for idx, chunk in enumerate(chunks):
    if idx == big:
        # replay only up to this chunk
        st = g.State(); st.abs_e = g.detect_settings(lines, dict(g.DEFAULTS))
        for j in range(idx):
            g.replay_lines(chunks[j], st)
        pro, segs2, tr = g.extract_layer(chunk, st.clone())
        for s in segs2[:8]:
            print("  (%8.3f,%8.3f)->(%8.3f,%8.3f) moves=%d lead=%d" % (
                s.start[0], s.start[1], s.end[0], s.end[1], len(s.moves), len(s.leading)))
        break
