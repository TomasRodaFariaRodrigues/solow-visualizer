from typing import NamedTuple

import numpy as np

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
    psi: float  # parameter to match literature
    u: float  # portion of time individuals spend developing human capital


def create_solow_params(A=2.0, s=0.3, alpha=0.3, delta=0.4, n=0.01, Tg=0.02, psi=0.1, u=1.0):
    """Creates a Solow model parameterization with default values"""
    return SolowParameters(A=A, s=s, alpha=alpha, delta=delta, n=n, Tg=Tg, psi=psi, u=u)


def g(k, params):
    """Law of motion for capital per capita, returning k_{t+1} given k_t"""
    A, s, alpha, delta, n, Tg, psi, u = params
    h = np.exp(psi * u)
    return k + A * h * (s * (k / (A * h)) ** alpha - (delta + Tg + n) * (k / (A * h)))


def exact_fixed_point(params):
    """Returns the steady state capital per capita, where accumulation is zero"""
    A, s, alpha, delta, n, Tg, psi, u = params
    h = np.exp(psi * u)
    return A * h * ((delta + Tg + n) / s) ** (1 / (alpha - 1))


def effective_scale(params):
    """Returns the effective-labour scale, technology times human capital"""
    return params.A * np.exp(params.psi * params.u)


k_annotation = r"$k^* = A_{(t)} \cdot h \cdot \left(\frac{\delta + g + n}{s}\right)^{\frac{1}{\alpha - 1}}$"


SolowLTechHCap_Params = (
    ParamSpec("A", "A — Labour-augmenting technology", 2.0, 0.1, 10.0, 0.1),
    ParamSpec("s", "s — Exogenous savings rate", 0.3, 0.01, 0.99, 0.01),
    ParamSpec("alpha", "α — Capital share of income/production", 0.3, 0.01, 0.95, 0.01),
    ParamSpec("delta", "δ — Capital depreciation rate", 0.4, 0.01, 1.0, 0.01),
    ParamSpec("n", "n — Population growth rate", 0.01, 0.0, 0.1, 0.001),
    ParamSpec("Tg", "g — Technological growth rate", 0.02, 0.0, 0.1, 0.001),
    ParamSpec("psi", "ψ — Parameter to match literature", 0.1, 0.0, 1.0, 0.01),
    ParamSpec("u", "u — Portion of time individuals spend developing human capital", 1.0, 0.0, 1.0, 0.01),
)


#####################################################################
###                          Model views                          ###
#####################################################################
## Steady state view ##
@register(
    "solow+ltech+humancap",
    "Model 3: Solow with technological growth and human capital",
    "45-degree diagram; each line is one parameterization",
    params=SolowLTechHCap_Params,
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
    specs=SolowLTechHCap_Params,
    evolution=transition.growing_technology,
    display=transition.PER_CAPITA,
)


@add_view("solow+ltech+humancap", "policy", "Policy transition", wants_shock=True)
def run_policy(fig, series):
    transition.run_paths(fig, series, POLICY)
