from typing import NamedTuple

from . import diagram, transition
from .registry import ParamSpec, add_view, register

#####################################################################
###               Parameters & Function definitions               ###
#####################################################################


class SolowParameters(NamedTuple):
    s: float  # savings rate
    alpha: float  # capital share of income
    delta: float  # depreciation rate
    n: float  # population growth rate


def create_solow_params(s=0.3, alpha=0.3, delta=0.4, n=0.01):
    """Creates a Solow model parameterization with default values"""
    return SolowParameters(s=s, alpha=alpha, delta=delta, n=n)


def g(k, params):
    """Law of motion for capital per capita, returning k_{t+1} given k_t"""
    s, alpha, delta, n = params
    return k + s * k**alpha - (delta + n) * k


def exact_fixed_point(params):
    """Returns the steady state capital per capita, where accumulation is zero"""
    s, alpha, delta, n = params
    return ((delta + n) / s) ** (1 / (alpha - 1))


def effective_scale(params):
    """Returns the effective-labour scale, which is 1 without technology"""
    return 1.0


k_annotation = r"$k^* = \left(\frac{\delta + n}{s}\right)^{\frac{1}{\alpha - 1}}$"


Solow_Params = (
    ParamSpec("s", "s — Exogenous savings rate", 0.3, 0.01, 0.99, 0.01),
    ParamSpec("alpha", "α — Capital share of income/production", 0.3, 0.01, 0.95, 0.01),
    ParamSpec("delta", "δ — Capital depreciation rate", 0.4, 0.01, 1.0, 0.01),
    ParamSpec("n", "n — Population growth rate", 0.01, 0.0, 0.1, 0.001),
)


#####################################################################
###                          Model views                          ###
#####################################################################
## Steady state view ##
@register(
    "solow",
    "Model 1: Base Solow",
    "45-degree diagram; each line is one parameterization",
    params=Solow_Params,
)
def run(fig, series):
    diagram.run_45(
        fig,
        series,
        create_solow_params,
        g,
        exact_fixed_point,
        annotation=k_annotation,
    )


## Policy transition view ##
POLICY = transition.PolicyModel(
    make_params=create_solow_params,
    law_of_motion=g,
    fixed_point=exact_fixed_point,
    effective_scale=effective_scale,
    specs=Solow_Params,
    evolution=transition.static_params,
    display=transition.PER_CAPITA,
)


@add_view("solow", "policy", "Policy transition", wants_shock=True)
def run_policy(fig, series):
    transition.run_paths(fig, series, POLICY)
