import streamlit as st

st.set_page_config(
    page_title="Probability Explorer",
    page_icon="📊",
    layout="wide"
)

pg = st.navigation({
    "": [
        st.Page("home.py", title="Home", icon="🏠"),
    ],

    "Probability Distributions": [
        st.Page("weibull.py", title="Weibull", icon="📈"),
        #st.Page("normal.py", title="Normal", icon="📊"),
        #st.Page("pages/exponential.py", title="Exponential", icon="⏱️"),
    ],

    "Reliability": [
        #st.Page("pages/reliability.py", title="Reliability Function", icon="🔧"),
        #st.Page("pages/hazard.py", title="Hazard Function", icon="⚠️"),
        ],

    "Simulation": [
        #st.Page("pages/monte_carlo.py", title="Monte Carlo", icon="🎲"),
    ],
})

pg.run()