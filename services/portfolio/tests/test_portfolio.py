"""Portfolio manager tests."""

from decimal import Decimal

from ai_trading_shared.domain.entities import Trade
from ai_trading_shared.domain.enums import Side, new_id
from portfolio.manager import PortfolioManager


def test_buy_and_mark() -> None:
    pm = PortfolioManager(Decimal("100000"))
    trade = Trade(
        id=new_id(),
        order_id=new_id(),
        ticker="AAPL",
        side=Side.BUY,
        quantity=Decimal("10"),
        price=Decimal("200"),
    )
    pm.apply_trade(trade, sector="Technology", country="US")
    snap = pm.mark_to_market({"AAPL": Decimal("210")})
    assert snap.cash == Decimal("98000")
    assert snap.equity == Decimal("100100")
    assert snap.positions[0].unrealized_pnl == Decimal("100")
