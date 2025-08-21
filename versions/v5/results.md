# Data Results

## Process
After relearning how SARIMAX worked and accidentally inspecting my model, I realized that the group companies were never being considered at all. Since this would not work on a SARIMAX model (as the companies never change), I switched back to LightGBM to accomodate for this. On average (across 100 runs) this actually barely outperforms `v4`, although the statistics (which are just off of one run and vary due to how LightGBM functions) seem otherwise.

## MAPE Statistics
- Overall
  - MAPE: 32.82%
  - MAE (Absolute Error in Days): 63.0 days
- 3rd Gen:
  - MAPE: 20.87%
  - MAE: 120.8 days
  - Range: 13 to 240
- 4th Gen:
  - MAPE: 36.60%
  - MAE: 55.7 days
  - Range: 10 to 138
- 5th Gen:
  - MAPE: 32.75%
  - MAE: 48.7 days
  - Range: 2 to 122
