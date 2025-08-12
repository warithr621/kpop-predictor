# Data Results

## Process
This uses the same information as `v1` (i.e. only the release dates of albums/EPs/singles), and uses LightGBM's decision tree as a prediction model.

## MAPE Statistics
- Overall: 32.86%
- 3rd Generation: 18.78%
- 4th Generation: 40.22%
- 5th Generation: 29.72%

## Insights
Despite the MAPE going down, there are a *lot* of interesting things to point out. The MAPE for 3rd generation is a lot lower than the other generations, which can likely be explained with two factors:
- As older groups, they will have way more albums to generate a conclusive regression
- Simultaneously as older groups, some of these have disbaned or just do not have a release yet this year, and are thus excluded from MAPE calculation

4th generation has a lot more variation, which makes sense since (I think) this contains the most groups. There's also a lot of variability in this, from IZ*ONE who have disbanded (and honestly I may exclude data because of this) to the irregular album releases of groups like ITZY.

5th generation doesn't have a lot of albums to make a prediction model off of, but the MAPE seems pretty stable in consideration of this.