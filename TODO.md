# TODO - GCODECrunch

## Active
- [ ] **Print validation**: Monitor the corrected single-perimeter LW-PLA wing. Record weight, wall thickness (root/mid/tip), surface finish, stringing, and actual print time. Compare measured weight against predicted ~20.7–21.3 g to confirm extrusion is correct.
- [ ] **Layer adhesion/buckling fixes**: If separation or buckling appears, test reduced fan (30–50% for LW), lower tip temp, Z-hop (0.2–0.3 mm), or bump the M221 tip floor to 55–60%.
- [ ] **Taper tuning**: Only after collecting the above measurements, tune the density/strength taper. Keep it linear to start, then consider a flow floor or knee if needed.

## Planned
- [ ] **PrusaSlicer profiles**: Create a proper eSun LW-PLA filament profile. Ensure Extrusion Multiplier remains 1.0 and apply the cooling threshold settings from the report.
- [ ] **Speed adjustments**: If print speed is still too slow, re-slice with the SPEED profile or adjust `Slow down if layer print time is below` and `Minimum print speed` accordingly.
- [ ] **GUI/howto revision**: Update the "Assumed printer / material settings" note in `src/main.py` to explicitly call out single-perimeter shells, travel priority, and cooling thresholds.
- [ ] **Testing/cleanup**: Add a feedrate regression test, expose Z-hop in the GUI, and regenerate the stale `wiki/GCODECrunch_Report.pdf`.
- [ ] **Documentation**: Expand single-perimeter guidance in `README.md` and wiki to match current workflow.