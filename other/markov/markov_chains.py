import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

class ContinuousTimeMarkov:
    def __init__(self, probs: np.ndarray, total_rate: float = 2.0, max_time: float = 50.0, initial_state: int = 1):
        self.probs = probs
        self.total_rate = total_rate  # Controls overall frequency of switching
        self.max_time = max_time
        self.initial_state = initial_state

    def simulate(self) -> list:
        k = len(self.probs)
        # Derive rates q01 and q10 from steady-state info
        q01 = self.probs * self.total_rate
        q10 = (1 - self.probs) * self.total_rate
        simulated_states = []
        for i in range(k):
            t = 0.0
            state = self.initial_state
            path = [(t, state)]
            while t < self.max_time:
                # Rate of leaving current state
                rate = q01[i] if state == 0 else q10[i]
                # Sample holding time from exponential distribution
                dt = np.random.exponential(1.0 / rate)
                t += dt
                if t >= self.max_time:
                    # Record final point up to max_time
                    path.append((self.max_time, state))
                    break
                # Transition to the other state
                state = 1 - state
                path.append((t, state))
            simulated_states.append(path)  
        return simulated_states

    def plot(self, states:list, title='Continuous-Time Markov Chain Simulation'):
        # Visualization for Continuous-Time Intervals
        fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(10, 8), sharex=True)
        for i, (ax, path) in enumerate(zip(axes, states)):
            # Draw horizontal blocks for each continuous state segment
            for j in range(len(path) - 1):
                t_start, state = path[j]
                t_end, _ = path[j+1]
                color = '#1f77b4' if state == 1 else '#b32a08'
                ax.hlines(y=state, xmin=t_start, xmax=t_end, linewidth=6, color=color)
            ax.set_ylabel(f'Node {i+1}\n($\\pi_1$={self.probs[i]:.2f})', rotation=0, labelpad=20, ha='center', va='center', fontsize=10)
            ax.set_yticks([0, 1])
            ax.set_ylim(-0.2, 1.2)
            ax.grid(True, linestyle='--', alpha=0.4, axis='x')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
        axes[-1].set_xlabel('Time ($t$)', fontsize=11, labelpad=10)
        # Main Title, Legend
        fig.suptitle(title, fontsize=14, fontweight='bold', y=0.96)
        legend_elements = [Line2D([0], [0], color='#1f77b4', lw=6, label='State 1'), Line2D([0], [0], color='#b32a08', lw=6, label='State 0')]
        fig.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, 0.91), ncol=2, frameon=False)
        plt.subplots_adjust(hspace=0.4, top=0.82)
        plt.show()

    @staticmethod
    def event_list_to_df(states: list) -> pd.DataFrame:
        """Convert simulated state trajectories into an event DataFrame."""
        data = [{"node": f"node_{i+1}", "time": t, "state": state,} for i, path in enumerate(states) for t, state in path]
        return (pd.DataFrame(data, columns=["node", "time", "state"]) .sort_values(["time", "node"], kind="stable") .reset_index(drop=True))

    def event_list_to_timegrid(self, states: list) -> pd.DataFrame:
        all_times = {0.0, self.max_time}
        for state in states:
            for t, s in state:
                all_times.add(t)
        timeline = sorted(list(all_times))
        self.timeline = timeline
        states_matrix = []
        for state in states:
            times = [s[0] for s in state]
            state_values = [s[1] for s in state]
            idx = np.searchsorted(times, timeline, side='right') - 1
            idx = np.clip(idx, 0, len(state_values) - 1)
            states_matrix.append([state_values[i] for i in idx])   
        # Transpose so rows correspond to timeline and columns correspond to nodes
        df = pd.DataFrame(states_matrix).T
        # Name columns after your nodes
        df.columns = [f"node_{i+1}" for i in range(len(states))]
        # Insert the timeline as the first column
        df.insert(0, 'timestamp', timeline)
        return df

    def calculate_collective_activity(self, df_time, condition_func=None):
        node_cols = [col for col in df_time.columns if col != 'timestamp']
        # Calculate the duration for each row (time until the next event timestamp)
        timestamps = df_time['timestamp'].values
        next_timestamps = np.append(timestamps[1:], self.max_time)
        durations = next_timestamps - timestamps
        # Determine inactive rows using either a custom condition or the default 
        if condition_func is not None:
            is_inactive = condition_func(df_time)
        else:
            # Default logic: inactive if all nodes are 0
            is_inactive = (df_time[node_cols] == 0).all(axis=1)   
        is_active = ~is_inactive                            
        # Sum total time spent in each state
        total_duration = self.max_time - timestamps[0]
        inactive_time = np.sum(durations[is_inactive])
        active_time = np.sum(durations[is_active])
        # Compute proportions
        prop_inactive = inactive_time / total_duration
        prop_active = active_time / total_duration
        return prop_inactive, prop_active

class TwoStateDiscreteMarkov:
    def __init__(self, params: np.ndarray = None, probs: np.ndarray = None, n_steps: int = 1000, initial_state: int = 1):
        self.params = params
        self.probs = probs if probs is not None else params[0]/(params[0]+params[1])
        self.n_steps = n_steps
        self.initial_state = initial_state

    def two_state_markov(self) -> pd.DataFrame:
        k = len(self.probs) if self.probs is not None else self.params.shape[1]
        states = np.zeros((k, self.n_steps), dtype=int)
        states[:, 0] = self.initial_state
        for t in range(1, self.n_steps):
            prev = states[:, t-1]
            r = np.random.rand(k)
            # Use probs if available, or fall back/adapt to params
            p = self.probs if self.probs is not None else self.params[0]
            # Transition 0 to 1 with prob p; 1 to 0 with prob (1-p)
            p_transition = np.where(prev == 0, p, 1 - p)
            states[:, t] = np.where(r < p_transition, 1 - prev, prev)
        return pd.DataFrame(states)

    def plot(self, df):
        fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(11, 8), sharex=True)
        for i, ax in enumerate(axes):
            row = df.iloc[i].values
            change_indices = np.where(np.diff(row) != 0)[0] + 1
            segments = np.split(row, change_indices)
            idx_splits = np.split(np.arange(len(row)), change_indices)
            # Draw horizontal bars for active segments
            for seg, idxs in zip(segments, idx_splits):
                if len(idxs) > 0:
                    if seg[0] == 1:
                        ax.hlines(y=1, xmin=idxs[0], xmax=idxs[-1], linewidth=6, color='#1f77b4')
                    elif seg[0] == 0:
                        ax.hlines(y=0, xmin=idxs[0], xmax=idxs[-1], linewidth=6, color="#b32a08")

            ax.set_ylabel(f'Node {i+1}\n($p$={self.probs[i]:.2f})', rotation=0, labelpad=25, ha='right', va='center', fontsize=10)
            ax.set_yticks([0, 1])
            ax.set_ylim(-0.2, 1.2)
            ax.grid(True, linestyle='--', alpha=0.4, axis='x')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
        axes[-1].set_xlabel('Time Steps', fontsize=11, labelpad=10)
        # Main Title
        fig.suptitle('Discrete Time Markov States', fontsize=14, fontweight='bold', y=0.96)
        # Global Figure Legend
        legend_elements = [Line2D([0], [0], color='#1f77b4', lw=6, label='State 1'), Line2D([0], [0], color='#b32a08', lw=6, label='State 0')]
        fig.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, 0.91), ncol=2, frameon=False)
        plt.subplots_adjust(hspace=0.4, top=0.82)
        plt.show()

if __name__ == "__main__":
    # Example Problem
    np.random.seed(123)
    params = np.array([np.random.normal(40, 5, size=4), np.random.normal(20, 3, size=4)])
    probs = params[0] / (params[0] + params[1]) # Beta parameters --> percentage 

    # Run simulation
    ctmc = ContinuousTimeMarkov(probs=probs, max_time=100.0)
    states = ctmc.simulate()
    print(f'Example state data: {states[0][:5]}')
    df = ctmc.event_list_to_df(states)
    print(df[df['time'] != 0].head(5))
    ctmc.plot(states)


