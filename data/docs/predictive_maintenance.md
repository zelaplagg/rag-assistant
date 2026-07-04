# Predictive Maintenance

Predictive maintenance (PdM) is a maintenance strategy that uses data and machine
learning to predict when equipment is likely to fail, so that maintenance can be
performed just in time — before a failure occurs but without replacing parts too
early.

## How it compares to other strategies

- **Reactive (run-to-failure):** fix equipment only after it breaks. Cheapest to
  start, but causes unplanned downtime and secondary damage.
- **Preventive (scheduled):** service equipment on a fixed schedule (e.g. every 500
  hours). Reduces failures but wastes life on parts replaced too early.
- **Predictive (condition-based):** use sensor data and models to act based on the
  actual condition of the equipment. Minimizes both downtime and wasted part life.

## Typical data sources

PdM models are usually trained on time-series sensor data such as temperature,
pressure, vibration, rotational speed, and flow. Because a single machine produces
many correlated signals over time, the data is high-dimensional and multivariate.

## Common machine-learning tasks

- **Fault classification:** predict whether the machine is in a healthy or degraded
  state (a classification problem).
- **Remaining Useful Life (RUL) estimation:** predict how many cycles remain before
  failure (a regression problem).
- **Anomaly detection:** flag readings that deviate from normal operating behavior.

## Why ensemble models work well

Ensemble methods such as Random Forest and gradient boosting (XGBoost) are popular
for PdM because they handle noisy, non-linear sensor relationships, are robust to
outliers, and provide feature-importance scores that help engineers interpret which
sensors drive a prediction.
