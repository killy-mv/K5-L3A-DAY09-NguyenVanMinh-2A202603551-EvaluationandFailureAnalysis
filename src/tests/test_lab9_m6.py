"""M6 reliability estimator regression tests (public, no LLM calls)."""
import math
import pytest

from lab9.stats import pass_at_k, pass_hat_k

pytestmark = pytest.mark.student


@pytest.mark.parametrize("n,c,k,at,hat", [
    (5, 5, 5, 1.0, 1.0),
    (5, 0, 5, 0.0, 0.0),
    (5, 4, 5, 1.0, 0.0),
    (5, 2, 3, 0.9, 0.0),
    (10, 8, 2, 44/45, 28/45),
    (10, 3, 3, 1 - 35/120, 1/120),
    (10, 3, 1, 0.3, 0.3),
])
def test_estimators_known_cases(n, c, k, at, hat):
    assert math.isclose(pass_at_k(n, c, k), at, abs_tol=1e-12)
    assert math.isclose(pass_hat_k(n, c, k), hat, abs_tol=1e-12)


@pytest.mark.parametrize("arguments", [
    (0, 0, 1), (5, -1, 1), (5, 6, 1),
    (5, 2, 0), (5, 2, 6), (5, 2, -1),
    (5.0, 2, 1), (5, 2.0, 1), (5, 2, 1.0),
    (True, 1, 1), (5, False, 1), (5, 2, True),
])
def test_rejects_invalid_counts(arguments):
    with pytest.raises(ValueError):
        pass_at_k(*arguments)
    with pytest.raises(ValueError):
        pass_hat_k(*arguments)


def test_reliability_monotonicity():
    for n in range(1, 15):
        for c in range(n + 1):
            prev_at, prev_hat = -1.0, 1.01
            for k in range(1, n + 1):
                at, hat = pass_at_k(n, c, k), pass_hat_k(n, c, k)
                assert 0 <= hat <= c/n + 1e-12
                assert c/n - 1e-12 <= at <= 1
                assert at >= prev_at - 1e-12
                assert hat <= prev_hat + 1e-12
                prev_at, prev_hat = at, hat
