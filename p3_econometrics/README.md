# Econometrics: OLS on UK Macro Data

OLS regression on real UK macroeconomic data (ONS/BoE, 2000–2023) looking at two well-known relationships: the Phillips Curve (unemployment → wage growth) and the Fisher equation (inflation → interest rates). Built from the normal equations rather than using statsmodels, because I wanted to understand what was being computed at each step.

## What it does

- OLS from scratch via `β̂ = (XᵀX)⁻¹Xᵀy`
- Three regressions: Phillips Curve, Fisher equation, multiple regression
- Standard diagnostic tests: Durbin-Watson (autocorrelation), Jarque-Bera (normality)
- Newey-West HAC standard errors as a comparison under residual dependence
- Chow structural break test (2022 split)
- Confidence bands computed analytically from the covariance matrix of the estimator
- Pre/post 2022 subsample comparison (only two observations in the later subsample)

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

**Durbin-Watson = 0.47** — well below 2, indicating strong positive autocorrelation. This motivates checking the conventional standard errors against an autocorrelation-robust estimate. In this sample, the Newey-West HAC calculation gives larger estimates: the intercept SE is 47% larger than OLS (1.65 vs 1.12), and the slope SE is 22% larger (0.24 vs 0.20). With n=24, the data-driven bandwidth formula gives m=1, so the calculation includes one lag; this does not establish that the remaining dependence is adequately represented. The Chow test for a structural break at 2022 gives F = 4.97, p = 0.018 under the classical test calculation. Residual dependence and a post-2022 subsample of only two observations limit the interpretation; this is not presented as a defensible rejection of stability.

**Fisher equation:** β̂ = 0.054 (not significantly different from 0, let alone 1). The model predicts rates should track inflation one-for-one. They didn't over this period — the BoE was stuck near the zero lower bound for most of 2010–2021, so rates barely moved while inflation varied.

**2022 structural break:** Splitting the sample at 2022 gives:
- Pre-2022: slope = -0.75, intercept = 7.81
- Post-2022: slope = -1.20, intercept = 12.34

With two observations and two fitted coefficients, the later line is saturated. The difference between these fitted lines does not identify a post-pandemic mechanism or provide a reliable estimate of a regime change.

## The simultaneity problem

The deepest issue: unemployment and wages are simultaneously determined. High wages reduce labour demand (→ higher unemployment). High unemployment reduces bargaining power (→ lower wages). OLS can't separate these because the assumption E[ε|X] = 0 is violated. The coefficient -0.95 captures correlation, not necessarily causation. Fixing this properly requires instrumental variables — something I know I'd need to add for a rigorous treatment.

## Running

```bash
pip install numpy pandas scipy matplotlib
python econometrics.py
```

Plots saved to `./plots/`: time series, Phillips Curve with confidence band, four-panel residual diagnostics, Fisher relationship.
