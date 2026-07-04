# NASA C-MAPSS Turbofan Dataset

C-MAPSS (Commercial Modular Aero-Propulsion System Simulation) is a turbofan engine
degradation dataset published by the NASA Prognostics Center of Excellence. It is a
standard benchmark for predictive maintenance and Remaining Useful Life research.

## Structure

The dataset contains run-to-failure trajectories for a fleet of simulated engines.
Each engine starts with different, unknown levels of initial wear and runs until it
fails. For every operating cycle, the data records:

- an engine unit number and a cycle index,
- 3 operational settings,
- 21 sensor measurements.

## Subsets

There are four subsets — FD001 to FD004 — that differ in the number of operating
conditions and fault modes:

- **FD001:** one operating condition, one fault mode (the simplest subset).
- **FD002:** six operating conditions, one fault mode.
- **FD003:** one operating condition, two fault modes.
- **FD004:** six operating conditions, two fault modes (the hardest subset).

## Typical use

FD001 is often used as a starting point because its single operating condition makes
the degradation signal easier to learn. Models trained on C-MAPSS commonly target
either fault-state classification or Remaining Useful Life regression.
