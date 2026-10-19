"""Shared drawing code for the 45-degree diagrams.

A model supplies the three things that differ between them: how a
parameterization is built, the law of motion, and the closed-form steady state.
Everything else lives here.
"""

import numpy as np

#####################################################################
###          Plot window and colours, shared by all models        ###
#####################################################################

# Default window on the k_t axis, widened at draw time when a steady state
# would otherwise fall outside it
K_MIN, K_MAX = 0.0, 6.0

# Room left to the right of the largest steady state, as a multiple of it
# (so that the steady state isn't at the very edge)
K_MAX_MARGIN = 1.3

# Anything drawn on the figure background rather than inside the axes
TEXT_COLOR = "#f7f7f7"
TITLE_SIZE = 13


#####################################################################
###                          Drawing                              ###
#####################################################################


def setup_45_axes(ax, k_max=K_MAX, fontsize=14):
    """Draws the 45 degree line and the axis labels, once per axes"""
    k_grid = np.linspace(K_MIN, k_max, 1200)
    ax.plot(k_grid, k_grid, "k--", lw=1, alpha=0.6, label="45°")
    ax.set_xlabel("$k_t$", fontsize=fontsize, color=TEXT_COLOR)
    ax.set_ylabel("$k_{t+1}$", fontsize=fontsize, color=TEXT_COLOR)
    ax.set_facecolor("#f7f7f7")
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.tick_params(axis="x", colors=TEXT_COLOR)
    ax.tick_params(axis="y", colors=TEXT_COLOR)


def plot_45(
    params,
    ax,
    law_of_motion,
    fixed_point,
    k_max=K_MAX,
    color=None,
    label=None,
    fontsize=12,
    annotation=None,
):
    """Draws one parameterization: its law of motion and its steady state"""
    k_grid = np.linspace(K_MIN, k_max, 1200)

    (line,) = ax.plot(
        k_grid,
        law_of_motion(k_grid, params),
        lw=2,
        alpha=0.8,
        color=color,
        label=label or "$g(k)$",
    )

    # The fixed point takes the colour of the line it belongs to
    kstar = fixed_point(params)
    ax.plot((kstar,), (kstar,), "o", ms=8, alpha=0.9, color=line.get_color())
    if annotation:
        ax.annotate(
            annotation,
            xy=(kstar, kstar),
            xycoords="data",
            xytext=(20, -20),
            textcoords="offset points",
            fontsize=fontsize,
        )
    return line


def run_45(fig, series, make_params, law_of_motion, fixed_point, annotation=None):
    """Draws the whole 45-degree diagram onto the figure supplied by the caller"""
    fig.patch.set_facecolor("#232323")

    ax = fig.add_subplot(111)
    ax.grid(color="#555555", alpha=0.2, lw=1, ls="--")
    shown = [s for s in series if s.visible]

    # Built once, since the window needs every steady state before the first
    # line can be drawn
    params = [make_params(**s.values) for s in shown]

    k_max = K_MAX
    for p in params:
        k_max = max(k_max, K_MAX_MARGIN * float(fixed_point(p)))

    setup_45_axes(ax, k_max=k_max)
    for s, p in zip(shown, params):
        plot_45(
            p,
            ax,
            law_of_motion,
            fixed_point,
            k_max=k_max,
            color=s.color,
            label=s.label,
            annotation=annotation,
        )
    ax.legend(loc="upper left", fontsize=11, frameon=False)
    return ax
