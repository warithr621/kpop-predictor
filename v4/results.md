# Data Results

## Process
In order to better resemble the time-forecasting nature of this project's goal, I switched to a common model used for this purpose: ARIMA. This specifically uses ARIMAX, which separates the data into endogenous (album/single/EP release dates) and exogenous (solo/subunit releases) data.

The model is also modified to calculate more detailed statistics.

## MAPE Statistics
- Overall
  - MAPE: 32.19%
  - MAE (Absolute Error in Days): 62.6 days
- 3rd Gen:
  - MAPE: 22.37%
  - MAE: 110.8 days
  - Range: 35 to 231
- 4th Gen:
  - MAPE: 34.37%
  - MAE: 54.2 days
  - Range: 7 to 147
- 5th Gen:
  - MAPE: 33.78%
  - MAE: 50.8 days
  - Range: 12 to 102

## Insights
To generate statistics and get an idea of feasibility, the model is trained on all releases prior to the beginning of 2025, and tries predicting the first 2025 release. Since some of the newer groups don't have enough pre-2025 data, which should only affect 5th-gen groups, they're excluded from these statistics.

One big realization is that despite the overall MAPE once again going down between versions, the 3rd-generation MAPE *did* go up a bit (although it is still by far the lowest). A big note is that this may honestly be due to the size of the training data. This comparison shows that with more and more dates (i.e. those from 3rd-gen groups with many more releases than more recent groups) will cause the MAPE to significantly decline over the years. However it does mean that the cutoff date (Dec. 31, 2024) has a way larger gap from the debut dates of 3rd gen groups (~2015) vs more recent groups (~2020).

The release data being used is really solid so far, so one of the best additions to make now is concert data and seeing how that functions as an exogenous variable. After that, the next steps would likely be upgrading from ARIMAX to **S**ARIMAX, and ensuring the model flows as one continuous structure. The latter point means that although the model will be predicting releases for groups individually, it should be able to interpret trends across all sorts of groups, generations, parent companies, etc.