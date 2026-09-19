import streamlit as st
import numpy as np
import matplotlib.pyplot as plt


# Page configuration
st.set_page_config(page_title="Weibull Distribution", page_icon="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSzUPFXruHJExdcFcJanBp0f_0hDhmMsu02JuV5HDDwbQ&s=10", layout="wide")

# Weibull functions
def weibull_pdf(t, lam, k, c):
    """
    Three-parameter Weibull probability density function.
    lam = scale parameter
    k   = shape parameter
    c   = location parameter
    """
    x = (t - c) / lam
    pdf = np.zeros_like(t, dtype=float)
    valid = t >= c
    pdf[valid] = ((k / lam) * x[valid] ** (k - 1) * np.exp(-x[valid] ** k))
    return pdf

def weibull_cdf(t, lam, k, c):
    """ Three-parameter Weibull cumulative distribution function. """
    x = (t - c) / lam
    cdf = np.zeros_like(t, dtype=float)
    valid = t >= c
    cdf[valid] = (1 - np.exp(-x[valid] ** k))
    return cdf

def weibull_reliability(t, lam, k, c):
    """Reliability function: R(t) = P(T > t)"""
    x = (t - c) / lam
    reliability = np.ones_like(t, dtype=float)
    valid = t >= c
    reliability[valid] = np.exp(-x[valid] ** k)
    return reliability

def weibull_hazard(t, lam, k, c):
    """ Weibull hazard function: h(t) = f(t) / R(t) """
    x = (t - c) / lam
    hazard = np.zeros_like(t, dtype=float)
    valid = t >= c
    hazard[valid] = ((k / lam) * x[valid] ** (k - 1))
    return hazard

# Sidebar
st.sidebar.title("Weibull Parameters")
lam = st.sidebar.slider("Scale parameter $\\lambda$", min_value=1.0, max_value=100.0, value=20.0, step=1.0)
k = st.sidebar.slider("Shape parameter k", min_value=0.2, max_value=5.0, value=2.0, step=0.1)
c = st.sidebar.slider("Location parameter c", min_value=0.0, max_value=50.0, value=0.0, step=1.0)
max_time = st.sidebar.slider("Maximum time", min_value=10, max_value=200, value=80, step=5)


# Main title
st.title("The Weibull Distribution")
st.markdown(
    """
The **Weibull distribution** is one of the most useful probability
distributions for modeling **time-to-failure**, **reliability**, and
**survival**.

It is particularly useful because its shape can represent different
types of failure behavior.
"""
)

# Mathematical definition
st.header("1. The Weibull Distribution")
st.latex(r""" f(t) = \frac{k}{\lambda} \left(\frac{t-c}{\lambda}\right)^{k-1} e^{-\left(\frac{t-c}{\lambda}\right)^k} """)
st.write("where:")
st.markdown(
    """
- **$\\lambda$** = scale parameter
- **k** = shape parameter
- **c** = location parameter
- **t** = time
"""
)
st.write(""" The three parameters allow the Weibull distribution to control the location, scale, and shape of the failure-time distribution. """)

# Parameter interpretation
st.header("2. What do the parameters mean?")
col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("Scale: $\\lambda$")
    st.write(f"Current value: **$\\lambda$ = {lam:.1f}**")
    st.info(""" $\\lambda$ controls the characteristic time scale of the distribution. Increasing $\\lambda$ generally shifts failures toward later times. """)

with col2:
    st.subheader("Shape: k")
    st.write(f"Current value: **k = {k:.1f}**")
    if k < 1:
        st.info(""" k < 1: Decreasing failure rate. Failures are more likely early in life. """)
    elif np.isclose(k, 1):
        st.info(""" k = 1: Constant failure rate. This is equivalent to the exponential distribution. """)
    else:
        st.info(""" k > 1: Increasing failure rate. Failures become more likely as time increases. """)

with col3:
    st.subheader("Location: c")
    st.write(f"Current value: **c = {c:.1f}**")
    st.info(""" c shifts the distribution along the time axis. The Weibull distribution begins at t = c. """)

# Create time values
t = np.linspace(0.001, max_time, 1000)
pdf = weibull_pdf(t, lam, k, c)
cdf = weibull_cdf(t, lam, k, c)
reliability = weibull_reliability(t, lam, k, c)
hazard = weibull_hazard(t, lam, k, c)

# PDF
st.header("3. Probability Density Function")
st.latex(r""" f(t) = \frac{k}{\lambda} \left(\frac{t-c}{\lambda}\right)^{k-1} e^{-\left(\frac{t-c}{\lambda}\right)^k} """)
# Create a narrower area for the plot
left, plot_col, right = st.columns([1, 3, 1])
with plot_col:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(t, pdf)
    ax.set_xlabel("Time")
    ax.set_ylabel("Probability density")
    ax.set_title("Weibull Probability Density Function", weight="bold")
    ax.grid(True)
    st.pyplot(fig)


# CDF and Reliability
st.header("4. Cumulative Probability and Reliability")
_,col1,col2,_ = st.columns([0.25, 2, 2, 0.25])
with col1:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(t, cdf)
    ax.set_xlabel("Time")
    ax.set_ylabel("F(t)")
    ax.set_title("Cumulative Distribution Function", weight="bold")
    ax.grid(True)
    st.pyplot(fig)

with col2:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(t, reliability)
    ax.set_xlabel("Time")
    ax.set_ylabel("R(t)")
    ax.set_title("Reliability Function", weight="bold")
    ax.grid(True)
    st.pyplot(fig)
st.latex(r""" R(t) = P(T>t) = 1-F(t) = e^{-\left(\frac{t-c}{\lambda}\right)^k} """)

# Hazard function
st.header("5. Hazard Function")
st.write(
    """
The hazard function represents the instantaneous failure rate,
conditional on the component surviving up to time t.
"""
)
st.latex(r""" h(t) = \frac{f(t)}{R(t)} = \frac{k}{\lambda} \left(\frac{t-c}{\lambda}\right)^{k-1} """)
left, plot_col, right = st.columns([1, 3, 1])
with plot_col:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(t, hazard)
    ax.set_xlabel("Time")
    ax.set_ylabel("Hazard")
    ax.set_title("Weibull Hazard Function", weight="bold")
    ax.grid(True)
    st.pyplot(fig)

# Reliability calculation
st.header("6. Reliability at a Specific Time")
time_point = st.number_input("Choose a time:", min_value=0.01, max_value=float(max_time), value=min(10.0, float(max_time)))
r = weibull_reliability(np.array([time_point]), lam, k, c)[0]
failure_probability = 1 - r
col1, col2 = st.columns(2)

with col1:
    st.metric("Reliability", f"{r:.3f}")

with col2:
    st.metric("Probability of failure", f"{failure_probability:.3f}")

st.write(f""" At time **$t$ = {time_point:.1f}**, the probability that the component is still operating is approximately **{r:.1%}**. """)

# Failure behavior
st.header("7. How $k$ changes failure behavior")
st.write(
    """
The shape parameter $k$ controls the behavior of the failure rate.

Changing $k$ allows the Weibull distribution to represent
different phases of a component's life.
"""
)
k_values = [0.5, 1.0, 2.0, 3.0]
left, plot_col, right = st.columns([1, 3, 1])

with plot_col:
    fig, ax = plt.subplots(figsize=(10, 5))

    for k_value in k_values:
        h = weibull_hazard(t, lam, k_value, c)
        ax.plot(t, h, label=f"$k$ = {k_value}")

    ax.set_xlabel("Time")
    ax.set_ylabel("Hazard")
    ax.set_title("Effect of the Shape Parameter k", weight="bold")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)

# Summary
st.header("8. Summary")
st.markdown(
    """
| Parameter | Meaning |
|---|---|
| **k < 1** | Decreasing failure rate |
| **k = 1** | Constant failure rate |
| **k > 1** | Increasing failure rate |
| **$\\lambda$** | Scale / characteristic time |
| **c** | Location / threshold |

The Weibull distribution is especially useful for reliability
analysis because the shape parameter **k** allows it to represent
**early-life failures, random failures, and wear-out failures**.
"""
)
