# FBS Ecosystem Strength Model

## Goal

Rank teams by the strength of the evidence in the full FBS competition graph.

The model does **not** order teams first by record or point differential. Those remain descriptive columns. The primary ranking is the fitted `latent_strength` from a weighted Bradley–Terry model applied to FBS-vs-FBS games, following the paired-comparison model introduced by Bradley and Terry (1952).

Reference: [Bradley and Terry (1952)](https://academic.oup.com/biomet/article/39/3-4/324/326091)

---

## 1. Game Layer

Each completed game involving at least one FBS team is exported to:

`data/processed/fbs_game_edges_YEAR.csv`

A decisive game becomes the directed result edge:

**L → W**

where:

- `L` = loser
- `W` = winner

Each edge retains:

- event ID
- date
- home team
- away team
- home score
- away score
- winner
- loser
- winner home/away status
- neutral-site flag
- margin
- source
- evidence weights

Ties are exported with:

`edge_direction = tie`

and do not create a directed win edge.

Only decisive FBS-vs-FBS games enter the FBS graph and latent-strength fit.

FBS-vs-FCS results still count toward an FBS team's record and scoring totals and appear in the event-level edge file. FCS schools are not FBS nodes.

### Score-Aware Edge Evidence

For winning score \(s_W\), losing score \(s_L\), and margin \(m=s_W-s_L\), the positive raw edge evidence is:

\[
q_g =
0.65\log(1+\min(m,35))
+
0.35\log\left(1+\frac{s_W+1}{s_L+1}\right)
\]

The margin cap limits the influence of extreme blowouts.

The score-ratio term distinguishes games such as:

- 35-7
- 35-28

even though both have the same winning score.

Raw evidence weights are normalized across decisive FBS-vs-FBS games by dividing each weight by the mean raw weight:

\[
\tilde q_g = \frac{q_g}{\operatorname{mean}(q)}
\]

Therefore, the mean normalized edge weight is one.

The same normalized evidence weight is used by:

1. the latent-strength model, and
2. the weighted graph diagnostics.

---

## 2. Team Observations

The team CSV reports separate evidence and diagnostic features.

### Record and Scoring

The following are calculated from **all completed games**, including FCS opponents:

- `record`
- `win_pct`
- `games_played`
- `points_for`
- `points_against`
- `point_diff`
- `points_per_game`
- `point_diff_per_game`

A bounded descriptive scoring feature is also reported:

\[
\text{score\_strength}
=
\tanh\left(
\frac{\text{point\_diff\_per\_game}}{21}
\right)
\]

This feature is descriptive only and does not directly determine the ranking.

### Opponent and Schedule Evidence

For FBS opponents, the following are reported:

- `opponent_win_pct`
- `strength_of_schedule`
- `weighted_sos`
- `quality_of_wins`
- `quality_of_losses`

Definitions:

**Opponent win percentage**

Mean season win percentage of the team's FBS opponents.

**Strength of schedule**

Mean fitted `latent_strength` of the team's FBS opponents.

**Weighted SOS**

Edge-evidence-weighted mean fitted strength of FBS opponents.

**Quality of wins**

Weighted fitted strength of FBS opponents that the team defeated.

**Quality of losses**

Weighted fitted strength of FBS opponents that defeated the team.

These quantities are diagnostic outputs. They are **not manually combined with rating coefficients** to produce the final ranking.

---

## 3. Latent Strength from Game Likelihood

For each FBS-vs-FBS game \(g\), let:

- \(W_g\) = winner
- \(L_g\) = loser
- \(S_i\) = latent strength of team \(i\)

The Bradley–Terry model estimates:

\[
P(W_g \text{ beats } L_g)
=
\sigma(S_{W_g}-S_{L_g})
\]

where:

\[
\sigma(x)
=
\frac{1}{1+e^{-x}}
\]

The weighted negative log-likelihood with L2 regularization is:

\[
\mathcal{L}(S)
=
\sum_g
\tilde q_g
\log\left(
1+e^{-(S_{W_g}-S_{L_g})}
\right)
+
\frac{\lambda}{2}
\sum_i S_i^2
\]

where:

- \(\tilde q_g\) is the normalized score-aware evidence weight
- \(\lambda\) is the regularization parameter
- the default is \(\lambda=0.25\)

The implementation should evaluate the logistic loss using a numerically stable formulation rather than directly computing potentially overflowing exponentials.

For example:

```python
loss = np.logaddexp(0.0, -(s_winner - s_loser))
```

Regularization keeps estimates finite for undefeated teams and stabilizes sparse or weakly connected schedules.

After fitting, the estimated strengths are centered to mean zero:

\[
S_i \leftarrow S_i-\operatorname{mean}(S)
\]

A one-unit difference in latent strength corresponds to odds of \(e:1\) under the Bradley–Terry model. It is **not** equivalent to one point per game.

The fitted `latent_strength` is the primary ranking variable.

The score-aware evidence weight makes a larger, score-supported margin more informative. It does **not** convert point margin directly into a team rating.

---

## 4. Network Evidence Columns

The following graph diagnostics are reported separately and do **not** enter the `latent_strength` ranking directly.

### Weighted PageRank

`weighted_pagerank`

PageRank flow over the weighted loser-to-winner graph.

A team's PageRank increases when weighted flow from other teams reaches that team through the competition network.

### HITS

`hits_authority`

Authority score from the weighted directed graph.

Winners accrue authority from teams that lost to them.

`hits_hub`

Hub score from the weighted directed graph.

A team receives hub strength when it points toward authoritative opponents.

### Katz Centrality

`katz_centrality`

An attenuated recursive incoming-path score using:

\[
\alpha=0.85
\]

and normalized edge weights.

Katz centrality captures both direct and indirect evidence while reducing the influence of increasingly distant paths.

### Eigenvector Centrality

`eigenvector_centrality`

Dominant incoming-evidence eigenvector computed using an identity-shifted power iteration.

The identity shift improves numerical stability while preserving the intended incoming-evidence interpretation.

### Weighted Degree Strength

`in_strength`

Total incoming edge weight.

This represents weighted FBS wins.

`out_strength`

Total outgoing edge weight.

This represents weighted FBS losses.

### Network Components

`network_component`

Identifier for the team's weakly connected FBS competition component.

`network_component_size`

Number of FBS teams in that weakly connected component.

These columns expose cases where the competition graph does not provide a direct path between groups of teams.

### Distance to Top Five

`distance_to_top5`

Shortest undirected game-network distance from the team to any of the five highest `latent_strength` teams.

A value of:

`-1`

means that no path exists because the team is disconnected from all five top teams.

---

## 5. Relationship Between the Game Graph and Bradley–Terry Model

The graph and the probability model represent the same competition evidence from different perspectives.

The stored graph uses:

**loser → winner**

to represent the observed result.

The Bradley–Terry model instead evaluates:

**winner versus loser**

through the probability:

\[
P(W \text{ beats } L)
=
\sigma(S_W-S_L)
\]

These representations are compatible.

The directed edge records **what happened**.

The Bradley–Terry model estimates the relative strengths that make the observed result more or less probable.

The edge evidence weight controls how strongly each observed game contributes to the likelihood.

---

## 6. Ranking

The primary ranking is based solely on:

`latent_strength`

Teams are sorted in descending order of fitted latent strength.

Team name is used only to break exact numerical ties.

The ranking therefore does **not** use:

- win percentage as the primary sort
- point differential as the primary sort
- head-to-head as a primary sort
- PageRank as a primary sort
- HITS as a primary sort
- SOS as a primary sort
- arbitrary manually selected rating coefficients

The output retains these measures as independent evidence and diagnostics.

The existing output filename is retained for compatibility:

`fbs_markov_rankings_YEAR.csv`

Although the filename contains `markov`, the primary ordering is now based on `latent_strength`.

The event-level directed graph is exported separately as:

`fbs_game_edges_YEAR.csv`

---

## 7. Data Sources and Game Deduplication

The analysis combines:

- `games_YEAR.csv`
- `team_schedules_YEAR.csv`

Completed games are deduplicated using the ESPN event ID.

If the schedule CSV is empty or unavailable, the analysis recovers completed games from cached FBS schedule HTML.

This prevents the ranking from silently operating on a scoreboard-only extract when additional completed schedule information is available.

---

## 8. Interpretation Limits

### Future Games

Scheduled future games do not affect the current estimate.

Only completed games contribute evidence.

### FCS Games

FCS games contribute to:

- record
- win percentage
- games played
- points scored
- points allowed
- point differential
- scoring diagnostics

They do **not** connect FBS teams in the latent-strength competition graph.

### Modeling Choices

The following are explicit modeling choices:

- score-aware edge formula
- 35-point margin cap
- 65/35 margin-to-score-ratio weighting
- Bradley–Terry formulation
- regularization parameter
- L2 regularization
- normalized edge weights
- absence of home-field adjustment
- absence of recency weighting

Small ranking gaps should therefore not be interpreted as statistically meaningful without sensitivity analysis.

### Disconnected Components

Relative strength is weakly identified across disconnected competition components.

Regularization shrinks sparse or weakly connected teams toward zero.

The following diagnostics expose this limitation:

- `network_component`
- `network_component_size`
- `distance_to_top5`

### Temporal Stability

The current model assumes team strength is reasonably stable over the season.

It does not currently model:

- home-field advantage
- injuries
- roster changes
- coaching changes
- transfer effects
- time-varying team strength
- recency weighting

These can be introduced in later model versions.

### Diagnostic Independence

PageRank, HITS, Katz, eigenvector centrality, SOS, record, and scoring statistics are complementary diagnostics.

They are not treated as interchangeable estimates of team strength and are deliberately not blended using arbitrary manually selected coefficients.

---

## 9. Model Philosophy

The central principle is:

> **The ranking should emerge from the structure and evidence of the competition ecosystem rather than from a predetermined ordering of record, score, or graph statistics.**

Record answers:

**How often did the team win?**

Score differential answers:

**By how much did the team tend to win or lose?**

Opponent strength answers:

**Who did the team play?**

The competition graph answers:

**How are those opponents connected to the rest of FBS?**

The Bradley–Terry model combines the individual game outcomes and their evidence weights into a single latent estimate:

**How strong does a team need to be for the observed collection of results to be plausible?**

That fitted latent strength is therefore the primary ranking signal, while the remaining statistics provide interpretable evidence for understanding *why* a team received its position.