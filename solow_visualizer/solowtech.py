from typing import NamedTuple

from . import diagram, transition
from .registry import ParamSpec, add_view, register

#####################################################################
###               Parameters & Function definitions               ###
#####################################################################


class SolowParameters(NamedTuple):
    A: float  # total factor productivity
    s: float  # savings rate
    alpha: float  # capital share of income
    delta: float  # depreciation rate
    n: float  # population growth rate
    Tg: float  # technological growth rate


def create_solow_params(A=2.0, s=0.3, alpha=0.3, delta=0.4, n=0.01, Tg=0.02):
    """Creates a Solow model parameterization with default values"""
    return SolowParameters(A=A, s=s, alpha=alpha, delta=delta, n=n, Tg=Tg)


def g(k, params):
    """Law of motion for capital per capita, returning k_{t+1} given k_t"""
    A, s, alpha, delta, n, Tg = params
    return k + A * (s * (k / A) ** alpha - (delta + Tg + n) * (k / A))


def exact_fixed_point(params):
    """Returns the steady state capital per capita, where accumulation is zero"""
    A, s, alpha, delta, n, Tg = params
    return A * ((delta + Tg + n) / s) ** (1 / (alpha - 1))


def effective_scale(params):
    """Returns the effective-labour scale, which here is technology alone"""
    return params.A


k_annotation = r"$k^* = A_{(t)} \cdot \left(\frac{\delta + g + n}{s}\right)^{\frac{1}{\alpha - 1}}$"


SolowLTech_Params = (
    ParamSpec("A", "A — Labour-augmenting technology", 2.0, 0.1, 10.0, 0.1),
    ParamSpec("s", "s — Exogenous savings rate", 0.3, 0.01, 0.99, 0.01),
    ParamSpec("alpha", "α — Capital share of income/production", 0.3, 0.01, 0.95, 0.01),
    ParamSpec("delta", "δ — Capital depreciation rate", 0.4, 0.01, 1.0, 0.01),
    ParamSpec("n", "n — Population growth rate", 0.01, 0.0, 0.1, 0.001),
    ParamSpec("Tg", "g — Technological growth rate", 0.02, 0.0, 0.1, 0.001),
)


#####################################################################
###                          Model views                          ###
#####################################################################
## Steady state view ##
@register(
    "solow+ltech",
    "Model 2: Solow with technological growth",
    "45-degree diagram; each line is one parameterization",
    params=SolowLTech_Params,
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
# A grows at Tg, so per-capita levels rise along a balanced path rather than
# achieving a constant steady state. The 45-degree view reads as the steady
# state of the initial period, which is where these paths start.
POLICY = transition.PolicyModel(
    make_params=create_solow_params,
    law_of_motion=g,
    fixed_point=exact_fixed_point,
    effective_scale=effective_scale,
    specs=SolowLTech_Params,
    evolution=transition.growing_technology,
    display=transition.PER_CAPITA,
)


@add_view("solow+ltech", "policy", "Policy transition", wants_shock=True)
def run_policy(fig, series):
    transition.run_paths(fig, series, POLICY)
