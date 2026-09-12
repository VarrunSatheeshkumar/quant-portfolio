# Econometrics: OLS on UK Macro Data

OLS regression on real UK macroeconomic data (ONS/BoE, 2000–2023) looking at two well-known relationships: the Phillips Curve (unemployment → wage growth) and the Fisher equation (inflation → interest rates). Built from the normal equations rather than using statsmodels, because I wanted to understand what was being computed at each step.

## What it does

- OLS from scratch via `β̂ = (XᵀX)⁻¹Xᵀy`
- Three regressions: Phillips Curve, Fisher equation, multiple regression
- Standard diagnostic tests: Durbin-Watson (autocorrelation), Jarque-Bera (normality)
- Newey-West HAC standard errors to correct for autocorrelation-induced bias
- Chow structural break test (2022 split)
- Confidence bands computed analytically from the covariance matrix of the estimator
- Pre/post 2022 subsample comparison (the Phillips Curve shifted materially)

## The maths

**OLS minimises:**

```
RSS = Σ(yᵢ - β̂₀ - β̂₁xᵢ)²
```

Taking partial derivatives and setting to zero gives the normal equations. In matrix form:

```
XᵀXβ̂ = Xᵀy  →  β̂ = (XᵀX)⁻¹Xᵀy
```

The standard errors come from `Var(β̂) = σ²(XᵀX)⁻¹` where `σ² = RSS/(n-k)`. The (n-k) denominator is the degrees-of-freedom correction — dividing by n would understate the error variance.

**When this is reliable:** Under the Gauss-Markov assumptions (linearity, no perfect multicollinearity, exogeneity, homoscedasticity, no autocorrelation), OLS is BLUE — Best Linear Unbiased Estimator. The problem is that macroeconomic data violates several of these.

## Results

**Phillips Curve:**
```
Wage Growth = 9.12 - 0.95 × Unemployment
R² = 0.51  (t-stat on slope = -4.77)
```
A 1pp rise in unemployment is associated with a 0.95pp fall in wage growth. The negative slope is consistent with the original Phillips (1958) relationship.

**Durbin-Watson = 0.47** — well below 2, indicating strong positive autocorrelation. This means the standard errors are understated and the t-statistics are inflated. I implemented Newey-West HAC standard errors to correct for this: the intercept SE is 47% larger than OLS (1.65 vs 1.12), and the slope SE is 22% larger (0.24 vs 0.20). With n=24, the data-driven bandwidth formula gives m=1, so first-order autocorrelation is corrected; with DW=0.47 there may be higher-order autocorrelation the one-lag correction doesn't fully capture. The Chow test for a structural break at 2022 gives F = 4.97, p = 0.018 — rejecting stability at 5%, though the post-2022 subsample has only 2 observations so this result should be treated as indicative.

**Fisher equation:** β̂ = 0.054 (not significantly different from 0, let alone 1). The model predicts rates should track inflation one-for-one. They didn't over this period — the BoE was stuck near the zero lower bound for most of 2010–2021, so rates barely moved while inflation varied.

**2022 structural break:** Splitting the sample at 2022 gives:
- Pre-2022: slope = -0.75, intercept = 7.81
- Post-2022: slope = -1.20, intercept = 12.34

The intercept shift is large — wages grew faster at the same unemployment rate post-pandemic, consistent with supply-side inflation and post-COVID expectation resetting.

## The simultaneity problem

The deepest issue: unemployment and wages are simultaneously determined. High wages reduce labour demand (→ higher unemployment). High unemployment reduces bargaining power (→ lower wages). OLS can't separate these because the assumption E[ε|X] = 0 is violated. The coefficient -0.95 captures correlation, not necessarily causation. Fixing this properly requires instrumental variables — something I know I'd need to add for a rigorous treatment.

## Running

```bash
pip install numpy pandas scipy matplotlib
python econometrics.py
```

Plots saved to `./plots/`: time series, Phillips Curve with confidence band, four-panel residual diagnostics, Fisher relationship.
