import scipy.stats as stats
import numpy as np
data = stats.weibull_min.rvs(2, size=50)
distributions = [stats.norm, stats.skewnorm, stats.lognorm, stats.gamma, stats.weibull_min, stats.expon,]

results = []
for dist in distributions:
    try:
        # Given data, fit params
        params = dist.fit(data)
        arg = params[:-2]
        loc = params[-2]
        scale = params[-1]
        
        # Calculate Log-Likelihood
        log_likelihood = np.sum(dist.logpdf(data, loc=loc, scale=scale, *arg))
        
        # Calculate BIC: ln(n) * k - 2 * ln(L)
        n = len(data)
        k = len(params)
        bic = np.log(n) * k - 2 * log_likelihood
        
        results.append((dist.name, bic, params))
    except Exception as e:
        # Skip distributions that fail to converge or match data bounds
        continue

# Sort results by lowest BIC (best fit)
results.sort(key=lambda x: x[1])
for rank, (name, bic, params) in enumerate(results, 1):
    print(f"{rank}: {name:<12}  BIC: {bic:.2f}")