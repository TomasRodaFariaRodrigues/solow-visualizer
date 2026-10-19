"""Central registry of runnable models.

A model module registers itself by decorating its run(fig, series) function
with @register and declaring the parameters it accepts as ParamSpecs. main.py
imports those modules for the side effect and reads REGISTRY to build the menu
and the parameter editor, so adding a model needs no changes to the GUI.

The app owns the list of Series, one per plotted line; the model draws whatever
it is handed.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Callable  # noqa: UP035

from matplotlib.figure import Figure

#####################################################################
###          Data the app and the models both work with           ###
#####################################################################


@dataclass(frozen=True)
class ParamSpec:
    """One tunable parameter of a model and the bounds the UI must respect"""

    name: str  # Keyword the model receives
    label: str  # Shown next to the widget
    default: float
    lo: float  # Minimum value allowed, so math is never broken
    hi: float  # Maximum value allowed, for the sake of realism
    step: float = 0.05

    def clamp(self, value: float) -> float:
        return min(max(value, self.lo), self.hi)


@dataclass
class Shock:
    """The policy experiment a line is subject to in the transition view"""

    # Reads as a sentence: "but now <parameter> <direction> by <amount>, from
    # period <t_shock>, simulated for <periods>". An empty parameter or a zero
    # amount means no policy, so the actual and counterfactual paths coincide.
    parameter: str = ""
    direction: str = "increases"
    amount: float = 0.0
    t_shock: float = 2
    periods: float = 60


@dataclass
class Series:
    """One line on the plot: a parameterization plus how to draw it"""

    values: dict[str, float] = field(default_factory=dict)
    label: str = "Line"
    color: str = "#1f77b4"
    visible: bool = True
    shock: Shock = field(default_factory=Shock)


@dataclass(frozen=True)
class View:
    """The two types of views: the default steady-state view, and the policy transition view"""

    key: str  # Unique within the model
    label: str  # Name shown in the view selector
    run: Callable[[Figure, Sequence[Series]], None]
    wants_shock: bool = False  # Whether the view's editor shows the policy editor


DEFAULT_VIEW_LABEL = "Steady state"


@dataclass(frozen=True)
class ModelEntry:
    key: str  # Short name, e.g. "solow"
    title: str  # Full name
    description: str
    params: tuple[ParamSpec, ...]  # Parameters for the parameter editor
    run: Callable[[Figure, Sequence[Series]], None]
    extra_views: list[View] = field(default_factory=list)

    def defaults(self) -> dict[str, float]:
        return {p.name: p.default for p in self.params}

    def views(self) -> tuple[View, ...]:
        """Returns the default view first, then any added by @add_view"""
        return (View("main", DEFAULT_VIEW_LABEL, self.run), *self.extra_views)


#####################################################################
###                    Registration decorators                    ###
#####################################################################

REGISTRY: dict[str, ModelEntry] = {}


def register(key, title, description="", params=()):
    """Adds the decorated run(fig, series) function to REGISTRY under key"""

    def decorator(fn):
        if key in REGISTRY:
            raise ValueError(f"duplicate model key: {key!r}")
        REGISTRY[key] = ModelEntry(key, title, description, tuple(params), fn)
        return fn

    return decorator


def add_view(model_key, view_key, label, wants_shock=False):
    """Adds another way of drawing an already registered model"""
    # The model keeps one menu entry and one list of lines; the view selector
    # chooses which of its run functions the app calls

    def decorator(fn):
        entry = REGISTRY.get(model_key)
        if entry is None:
            raise ValueError(f"no model registered as {model_key!r}")
        if any(v.key == view_key for v in entry.views()):
            raise ValueError(f"duplicate view {view_key!r} on {model_key!r}")
        entry.extra_views.append(View(view_key, label, fn, wants_shock))
        return fn

    return decorator
