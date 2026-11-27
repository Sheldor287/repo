import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import colormaps
import statsmodels.formula.api as smf
from scipy.stats import boxcox
import statsmodels.api as sm


class Analysis:
    def __init__(self, path):
        self.path = path
        self.df = None
        
        # column names centralized
        self.cls_parent = "cls_parent"
        self.cls_child = "cls_child"
        
        # results storage
        self.ols_results = None
        self.boxcox_results = None

    def load_data(self):
        df = pd.read_excel(self.path)
        df["Score"] = ((df["Time Delivered"] - df["Time Loaded"]).dt.total_seconds() / 60)
        df["num_days"] = (df["Date"] - df["Date"].min()).dt.days
        self.df = df
        return self

    def plot_quantiles(self, n_bins=10):
        df = self.df
        
        SV_list = df[self.cls_parent].unique()
        ST_list = df[self.cls_child].unique()

        base_cmap = colormaps['gist_rainbow'].resampled(20)
        colors = base_cmap(np.arange(20))
        np.random.shuffle(colors)
        st_color_dict = dict(zip(ST_list, colors))

        n_cols = 2
        n_rows = int(np.ceil(len(SV_list) / n_cols))

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, 4*n_rows), sharex=True, sharey=True)
        axes = axes.flatten()

        all_handles = {}

        for i, cls_parent in enumerate(SV_list):
            ax = axes[i]
            subset_sv = df[df[self.cls_parent] == cls_parent]

            for cls_child in ST_list:
                subset_st = subset_sv[subset_sv[self.cls_child] == cls_child]
                if subset_st.empty:
                    continue

                subset_st = subset_st.copy()
                subset_st["x_bin"] = pd.qcut(subset_st["num_days"], n_bins, duplicates='drop')

                quant_df = subset_st.groupby("x_bin", observed=False)["Score"].quantile([0.25,0.5,0.75]).unstack()
                quant_df.columns = ["q25","q50","q75"]
                quant_df["x_center"] = quant_df.index.map(lambda b: b.mid)

                color = st_color_dict[cls_child]
                line, = ax.plot(quant_df["x_center"], quant_df["q50"], color=color)
                ax.fill_between(quant_df["x_center"], quant_df["q25"], quant_df["q75"], alpha=0.2, color=color)

                if cls_child not in all_handles:
                    all_handles[cls_child] = line

            ax.set_title(f"{cls_parent}")
            ax.set_xlabel("Days")
            ax.set_ylabel("Score")

        fig.legend(all_handles.values(), all_handles.keys(), title="cls_child",bbox_to_anchor=(1.05, 0.95), loc="upper left")
        plt.tight_layout()
        plt.show()

    def run_rlm(self):
        df = self.df
        results = []

        for (cls_parent, cls_child), group in df.groupby([self.cls_parent, self.cls_child]):
            model = smf.rlm("Score ~ num_days", data=group).fit()
            ci = model.conf_int().loc["num_days"]
            results.append({"cls_parent": cls_parent,"cls_child": cls_child, "coef_30days": 30 * model.params["num_days"],"p_value": model.pvalues["num_days"],"L_CI": ci[0],"U_CI": ci[1],})

        self.ols_results = pd.DataFrame(results).sort_values("p_value")
        return self.ols_results

    def run_boxcox_analysis(self):
        df = self.df
        results = []
        qq_residuals = []

        for (cls_parent, cls_child), group in df.groupby([self.cls_parent, self.cls_child]):

            y = group["Score"].values
            y_shifted = y - y.min() + 1e-6
            y_bc, lam = boxcox(y_shifted)

            group_bc = group.copy()
            group_bc["Score_bc"] = y_bc

            model = smf.rlm("Score_bc ~ num_days", data=group_bc).fit()

            # inverse transform delta
            y0 = model.predict({"num_days": [0]})[0]
            y1 = model.predict({"num_days": [30]})[0]

            if lam == 0:
                y0_orig = np.exp(y0)
                y1_orig = np.exp(y1)
            else:
                y0_orig = (y0 * lam + 1)**(1/lam) + y.min() - 1e-6
                y1_orig = (y1 * lam + 1)**(1/lam) + y.min() - 1e-6

            results.append({"cls_parent": cls_parent,"cls_child": cls_child,"delta_30days": y1_orig - y0_orig,"p_value": model.pvalues["num_days"],"lambda": lam})
            qq_residuals.append((f"{cls_parent}-{cls_child}", model.resid))

        self.boxcox_results = pd.DataFrame(results).sort_values("p_value")

        # QQ plots
        self._plot_qq(qq_residuals)
        return self.boxcox_results


    def _plot_qq(self, qq_residuals):
        n = len(qq_residuals)
        n_cols = 4
        n_rows = (n + n_cols - 1) // n_cols

        plt.figure(figsize=(4*n_cols, 4*n_rows))

        for i, (label, resid) in enumerate(qq_residuals, 1):
            ax = plt.subplot(n_rows, n_cols, i)
            sm.qqplot(resid, line='45', ax=ax)
            ax.set_title(label)

        plt.tight_layout()
        plt.show()


if __name__ == "__main__":

    analysis = Analysis("path.xlsx")
    analysis.load_data()
    analysis.plot_quantiles(n_bins=10)
    ols_results = analysis.run_rlm()
    print(ols_results)
    boxcox_results = analysis.run_boxcox_analysis()
    print(boxcox_results)