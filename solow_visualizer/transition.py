"""Simulation and drawing for the policy transition view.

Capital is the only state variable, so one iteration over k yields all four
panels, with output, saving and consumption following from it in the same
period:

    y_t = E^(1-alpha) * k_t^alpha       output
    i_t = s * y_t                       saving
    c_t = (1 - s) * y_t                 consumption

E is the effective-labour scale and the only quantity the models differ by:
1 for the base model, A with labour-augmenting technology, and A*h with human
capital. Each model supplies it.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from matplotlib.lines import Line2D

from . import diagram
from .registry import ParamSpec, Series

#####################################################################
###            Defaults for the transition experiment             ###
#####################################################################

DEFAULT_T_SHOCK = 2
DEFAULT_PERIODS = 60

INCREASES, DECREASES = "increases", "decreases"
DIRECTIONS = (INCREASES, DECREASES)
T_SHOCK_SPEC = ParamSpec("t_shock", "from period", DEFAULT_T_SHOCK, 0, 40, 1)
PERIODS_SPEC = ParamSpec("periods", "over periods", DEFAULT_PERIODS, 10, 300, 10)


#####################################################################
###   Conventions - a model names one evolution and one display   ###
#####################################################################


def static_params(params, t):
    """Parameters that do not move on their own"""
    return params


def growing_technology(params, t):
    """Grows A at the technological growth rate, so levels rise over time"""
    return params._replace(A=params.A * (1 + params.Tg) ** t)


def _levels(k, params_by_period, effective_scale):
    """Returns the effective scale, the saving rate and output, period by period"""
    scale = np.array([float(effective_scale(p)) for p in params_by_period])
    alpha = np.array([float(p.alpha) for p in params_by_period])
    saving_rate = np.array([float(p.s) for p in params_by_period])
    output = scale ** (1 - alpha) * k**alpha
    return scale, saving_rate, output


def _per_capita(k, params_by_period, effective_scale):
    scale, s, y = _levels(k, params_by_period, effective_scale)
    return {"k": k, "y": y, "c": (1 - s) * y, "i": s * y}


@dataclass(frozen=True)
class Display:
    """One way of expressing the paths, and the wording for its axis labels"""

    transform: Callable
    unit: str


PER_CAPITA = Display(_per_capita, "per worker")


#####################################################################
###             The contract a model offers this view             ###
#####################################################################


@dataclass(frozen=True)
class PolicyModel:
    make_params: Callable  # Values dict to the model's parameter tuple
    law_of_motion: Callable  # (k, params) to k next period
    fixed_point: Callable  # Params to steady state, used as the starting k
    effective_scale: Callable  # Params to E
    specs: Sequence[ParamSpec]  # Which keys of Series.values are economic
    evolution: Callable = static_params
    display: Display = PER_CAPITA

    def params_from(self, series: Series):
        """Builds this model's parameter tuple from a Series' values"""
        # Filtered by spec name, so keys belonging to another view cannot reach it
        names = {spec.name for spec in self.specs}
        return self.make_params(**{k: v for k, v in series.values.items() if k in names})

    def shocked(self, params, shock):
        """Applies the policy, clamped to the bounds the model declared"""
        spec = next((s for s in self.specs if s.name == shock.parameter), None)
        if spec is None or not shock.amount:
            return params
        step = shock.amount if shock.direction == INCREASES else -shock.amount
        moved = spec.clamp(getattr(params, spec.name) + step)
        return params._replace(**{spec.name: moved})


#####################################################################
###                          Simulation                           ###
#####################################################################


def params_by_period(model, before, after, t_shock, periods):
    """One parameter tuple per period, with the policy in force from t_shock"""
    # Evolution is applied on top, so a growing A is accounted for
    return [model.evolution(before if t < t_shock else after, t) for t in range(periods + 1)]


def capital_path(model, per_period, k0):
    """Iterates the law of motion using each period's own parameters"""
    k = np.empty(len(per_period))
    k[0] = k0
    for t in range(len(per_period) - 1):
        k[t + 1] = model.law_of_motion(k[t], per_period[t])
    return k


def paths(model, params, shock):
    """Returns the counterfactual and actual paths, both simulated"""
    t_shock = int(shock.t_shock)
    periods = int(shock.periods)
    after = model.shocked(params, shock)

    without = params_by_period(model, params, params, t_shock, periods)
    with_policy = params_by_period(model, params, after, t_shock, periods)

    k0 = float(model.fixed_point(model.evolution(params, 0)))
    transform = model.display.transform
    return (
        transform(capital_path(model, without, k0), without, model.effective_scale),
        transform(capital_path(model, with_policy, k0), with_policy, model.effective_scale),
    )


#####################################################################
###                           Drawing                             ###
#####################################################################

# The four panels, in the order they are laid out 2x2
PANELS = (
    ("k", "Capital"),
    ("y", "Output"),
    ("c", "Consumption"),
    ("i", "Saving"),
)

TEXT_COLOR = diagram.TEXT_COLOR  # Text on the figure: titles, tick labels
AXES_TEXT_COLOR = "#232323"  # Text inside a panel, where the ground is light
FIG_FACECOLOR = "#232323"
AXES_FACECOLOR = "#f7f7f7"
GRID_COLOR = "#555555"
SHOCK_LINE_COLOR = "#888888"


def _setup_panel(ax, title, xlabel=None, fontsize=10):
    """Draws the structure every panel shares"""
    ax.set_facecolor(AXES_FACECOLOR)
    ax.grid(color=GRID_COLOR, alpha=0.2, lw=1, ls="--")
    ax.set_title(title, color=TEXT_COLOR, fontsize=fontsize + 1)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=fontsize, color=TEXT_COLOR)
    ax.tick_params(axis="x", colors=TEXT_COLOR, labelsize=fontsize - 1)
    ax.tick_params(axis="y", colors=TEXT_COLOR, labelsize=fontsize - 1)


def run_paths(fig, series, model):
    """Draws the four transition panels onto the figure supplied by the caller"""
    fig.patch.set_facecolor(FIG_FACECOLOR)
    axes = fig.subplots(2, 2).ravel()
    shown = [s for s in series if s.visible]

    unit = model.display.unit
    for index, (key, name) in enumerate(PANELS):
        ax = axes[index]
        bottom_row = index >= 2
        _setup_panel(ax, f"{name} {unit}", xlabel="$t$" if bottom_row else None)

        for s in shown:
            without, with_policy = paths(model, model.params_from(s), s.shock)
            t = np.arange(len(without[key]))
            ax.plot(t, without[key], lw=1.4, ls="--", alpha=0.7, color=s.color)
            ax.plot(t, with_policy[key], lw=2, alpha=0.9, color=s.color)

        # All lines share the axis, so mark the first line's date only
        if shown:
            ax.axvline(
                int(shown[0].shock.t_shock),
                color=SHOCK_LINE_COLOR,
                lw=1,
                ls=":",
                alpha=0.8,
            )

    _draw_legend(axes[0], shown)
    fig.tight_layout(rect=(0, 0, 1, 0.95))  # Leaves the top strip for the title
    return axes


def _draw_legend(ax, shown):
    """Names the lines once and says which line style is which"""
    # Sits inside a panel, so its text follows the axes rather than the figure
    handles = [
        Line2D([], [], color=AXES_TEXT_COLOR, lw=2, label="with the policy"),
        Line2D([], [], color=AXES_TEXT_COLOR, lw=1.4, ls="--", label="counterfactual"),
    ]
    handles += [Line2D([], [], color=s.color, lw=2, label=s.label) for s in shown]
    legend = ax.legend(
        handles=handles,
        loc="best",
        fontsize=8,
        frameon=True,
        facecolor=AXES_FACECOLOR,
        edgecolor="#cccccc",
        framealpha=0.9,
    )
    for text in legend.get_texts():
        text.set_color(AXES_TEXT_COLOR)
