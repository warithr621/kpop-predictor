# Data Results

## Process
This uses the same information as `v2`, but additionally uses data points from solo releases. Specifically, it takes into account the number of solo/subunit releases (separate from the group) in different time intervals (e.g. the past 6 months or the past year) and adds this as a factor in the LightGBM model.

## MAPE Statistics
- Overall: $33.11 \pm 1.5$%
- 3rd Generation: $18.32$%
- 4th Generation: $34.98$%
- 5th Generation: $36.76$%

## Insights
One crucial thing to note is that the significant difference in solos can play a role in worse MAPE in later generations. Most 3rd generation groups have existed long enough to have multiple (if not all) members go on to release solo music, whereas many 4th generation (and all 5th generation) groups have no members that have done so.