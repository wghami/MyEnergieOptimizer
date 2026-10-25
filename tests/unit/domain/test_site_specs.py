"""Site descriptions refuse ambiguous ids."""

from collections.abc import Callable
from decimal import Decimal

import pytest

from myenergy.domain.contract import Contract
from myenergy.domain.errors import SiteError
from myenergy.domain.profiles import AsMeasured, ProfileRef, Shaped
from myenergy.domain.sites import AssetSpec, ShareDirection, ShareSpec, SiteSpec

CONTRACT = Contract(pack="p", subscribed_kva=Decimal(6))
PROFILE = Shaped(ref=ProfileRef(source="s", key="k"), scaling=AsMeasured())


def test_a_site_with_assets_and_shares() -> None:
    site = SiteSpec(
        id="home",
        contract=CONTRACT,
        assets=(AssetSpec(id="house", kind="consumer", profile=PROFILE),),
        shares=(
            ShareSpec(direction=ShareDirection.IN, counterparty="op", profile=PROFILE),
            ShareSpec(direction=ShareDirection.OUT, counterparty="op", profile=PROFILE),
        ),
    )
    assert [asset.id for asset in site.assets] == ["house"]


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda: AssetSpec(id="", kind="pv"), "needs an id and a kind"),
        (lambda: AssetSpec(id="a", kind=""), "needs an id and a kind"),
        (
            lambda: ShareSpec(direction=ShareDirection.IN, counterparty="", profile=PROFILE),
            "needs a counterparty",
        ),
        (lambda: SiteSpec(id="", contract=CONTRACT), "needs an id"),
        (
            lambda: SiteSpec(id="s", contract=CONTRACT, assets=(AssetSpec(id="a", kind="pv"),) * 2),
            "repeats an asset id",
        ),
        (
            lambda: SiteSpec(
                id="s",
                contract=CONTRACT,
                shares=(ShareSpec(direction=ShareDirection.IN, counterparty="op", profile=PROFILE),)
                * 2,
            ),
            "shares twice",
        ),
    ],
)
def test_ambiguous_descriptions_are_refused(make: Callable[[], object], message: str) -> None:
    with pytest.raises(SiteError, match=message):
        make()
