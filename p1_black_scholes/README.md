# Black-Scholes Options Pricing

I built this after reading about options and wanting to actually implement the pricing formula rather than just use a library. The mathematics turned out to be more interesting than I expected — particularly the part about why the expected return of the stock doesn't appear in the formula at all.

## What it does

- Prices European calls and puts using the Black-Scholes formula
- Computes all five Greeks (Delta, Gamma, Theta, Vega, Rho)
- Solves for implied volatility using Newton-Raphson
- Includes a binomial tree implementation as a cross-check, which also handles American options
- Demonstrates the volatility smile — the model's most visible real-world failure

## The maths

**The formula:**

```
C = S·N(d₁) - K·e^{-rT}·N(d₂)

d₁ = [ln(S/K) + (r + σ²/2)·T] / (σ√T)
d₂ = d₁ - σ√T
```

The σ²/2 term in d₁ is the Ito correction — it comes from applying the chain rule to ln(S) for a stochastic process. Without it the expected value of the stock price is wrong. This is one of the places where ordinary calculus gives the wrong answer for random processes.

The result I find most interesting: the expected return μ of the stock doesn't appear in the formula. The reason is the replication argument — if you hold -Δ shares for every call you own, the position is momentarily riskless (small stock moves cancel out). A riskless portfolio must earn the risk-free rate r. So the option price depends on r, not on what you think the stock will do.

**Greeks** measure how the option price changes with each input:

| Greek | Formula | Intuition |
|-------|---------|-----------|
| Delta | N(d₁) | Hedge ratio — shares to sell per option held |
| Gamma | N'(d₁)/(Sσ√T) | Rate of change of delta |
| Theta | ... | Daily time decay |
| Vega  | S·N'(d₁)·√T/100 | Per 1% change in vol |
| Rho   | K·T·e^(-rT)·N(d₂)/100 | Per 1% change in rate |

**Implied volatility** is found using Newton-Raphson. Given a market price, find the σ that makes BS equal that price. Works because vega is always positive — the price is strictly increasing in σ, so there's exactly one solution and Newton-Raphson always converges.

**Binomial tree** (Cox-Ross-Rubinstein): discretise time into N steps, price goes up by u = e^(σ√Δt) or down by d = 1/u at each step. As N→∞ it converges to the BS price for European options. The advantage: it can handle American options by checking early exercise at each node, which BS can't do.

## Where it breaks

**The volatility smile** is the most obvious failure. If BS were correct, implied vol would be flat across strikes. It isn't — OTM puts trade at higher IV than ATM options because the market prices in crash risk that the lognormal distribution ignores. The skew became a permanent feature of equity markets after 1987.

Other assumptions that fail in practice:
- Constant volatility (it's stochastic and mean-reverting)
- Log-normal returns (real returns have fat tails and negative skew)
- Continuous trading (rebalancing is discrete and costly)

## Running

```bash
pip install numpy scipy matplotlib
python black_scholes.py
```

## Output

Prices, Greeks, IV round-trip check, binomial tree convergence table, and four plots saved to `./plots/`.

Sample output for S=100, K=100, T=0.5yr, r=5%, σ=20%:
```
Call: £6.8887
Put:  £4.4197
Put-call parity: ✓
American put early-exercise premium: £0.24
```
