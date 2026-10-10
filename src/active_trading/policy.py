"""Shared, allocation-based limits; caller configuration is the trust boundary."""
from decimal import Decimal, InvalidOperation
from pathlib import Path


class PolicyError(ValueError):
    """A risk policy or balance is missing, ambiguous or invalid."""


def _decimal(value, label, *, positive=True):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise PolicyError(label + " must be numeric")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise PolicyError(label + " must be numeric") from exc
    if not result.is_finite() or result < 0 or (positive and not result):
        raise PolicyError(label + " must be finite and positive/nonnegative")
    return result


def load_policy(path=None):
    """Read the effective specification without permitting duplicate JSON keys."""
    if path is None:
        path = Path(__file__).resolve().parents[2] / "spec" / "strategy_spec.provisional.json"
    # Central strict JSON helper is also used by the CLIs; no parser dependency.
    from active_trading.jsonio import load_json
    return load_json(Path(path))


def capital_limits(policy, account_balance):
    """Use min(strategy allocation, account balance), never the full large account."""
    try:
        risk = policy["risk"]
        allocation = _decimal(risk["strategy_allocation_usd"], "strategy allocation")
        balance = _decimal(account_balance, "account balance")
        basis = min(allocation, balance)
        count = risk["maximum_positions"]
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise PolicyError("maximum_positions must be a positive integer")
        result = {"basis": basis, "maximum_positions": count}
        for output, field in (("name_cap", "maximum_name_weight"),
                              ("gross_cap", "maximum_gross_weight_including_pending"),
                              ("position_risk_budget", "position_overnight_risk_fraction"),
                              ("night_loss_limit", "single_night_loss_fraction"),
                              ("drawdown_limit", "drawdown_fraction")):
            fraction = _decimal(risk[field], field)
            if fraction > 1:
                raise PolicyError(field + " must be at most one")
            result[output] = basis * fraction
        if result["name_cap"] > result["gross_cap"]:
            raise PolicyError("Per-name cap exceeds gross cap")
        return result
    except (KeyError, TypeError) as exc:
        raise PolicyError("Complete allocation-based risk policy is required") from exc
