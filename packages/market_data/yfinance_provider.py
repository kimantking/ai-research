"""yfinance 공급자 (선택 — 패키지가 설치돼 있을 때만).

★ 왜 '선택' 인가

    yfinance 는 pip 설치가 필요합니다. 이 프로젝트의 원칙은
    "외부 패키지 없이도 전부 돈다" 이므로, 있으면 쓰고 없으면
    **오류가 아니라 '미설치'** 로 보고합니다.

★ 약관 (중요)

    Yahoo Finance 데이터는 **개인 연구·비상업 용도**를 전제로 합니다.
    재배포·상업적 서비스 제공은 허용되지 않습니다.
    이 프로젝트는 로컬 연구 도구이므로 그 범위 안에 있지만,
    **외부에 공개 배포할 때는 반드시 다시 확인해야 합니다** (§승인 필요 항목).

★ 검증 상태
    ❌ 이 개발 환경에서는 설치조차 불가능했습니다(PyPI 차단).
    코드는 yfinance 공개 API 기준으로 작성했고, 실제 동작은
    antking님 PC 에서 처음 확인됩니다. 실패해도 시스템은 멈추지 않습니다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .base import Bar, Bars, MarketDataError, ProviderResult, check_quality


class YFinanceProvider:
    id = "yfinance"
    name = "Yahoo Finance (yfinance)"
    requires_key = False
    terms_note = (
        "Yahoo 데이터는 개인 연구·비상업 용도 전제입니다. "
        "재배포 금지. 외부 공개 배포 전에 약관을 반드시 재확인하십시오."
    )
    verified = "미검증 — 이 개발 환경에서 설치 불가(PyPI 차단)"

    def __init__(self, exchange: str | None = "XNYS", auto_adjust: bool = False):
        # auto_adjust=False 로 두는 이유:
        #   조정주가는 과거 값이 '나중에' 바뀝니다. 그것을 그대로 백테스트에
        #   쓰면 그 시점에 알 수 없던 정보(미래의 분할·배당)가 섞입니다.
        #   원주가를 받고, 조정이 필요하면 명시적으로 합니다.
        self.exchange = exchange
        self.auto_adjust = auto_adjust

    # ------------------------------------------------------------------
    @staticmethod
    def is_installed() -> bool:
        try:
            import yfinance  # noqa: F401
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    def fetch(self, symbol: str, start: str | None = None,
              end: str | None = None) -> ProviderResult:
        if not self.is_installed():
            return ProviderResult(
                ok=False,
                error=("yfinance 가 설치되어 있지 않습니다. "
                       "필요하면 .\\update.ps1 -WithData 로 설치하거나, "
                       "Stooq/CSV 공급자를 쓰십시오. (오류가 아닙니다)"),
            )
        try:
            import yfinance as yf

            df = yf.Ticker(symbol).history(
                start=start, end=end, interval="1d",
                auto_adjust=self.auto_adjust, actions=False,
            )
            if df is None or len(df) == 0:
                return ProviderResult(
                    ok=False, error=f"{symbol}: 반환된 데이터가 없습니다")
            bars = self._from_dataframe(df, symbol)
        except MarketDataError as exc:
            return ProviderResult(ok=False, error=str(exc))
        except Exception as exc:
            return ProviderResult(ok=False, error=f"yfinance 오류: {exc}")

        quality = check_quality(bars, exchange=self.exchange)
        return ProviderResult(ok=True, bars=bars, quality=quality)

    # ------------------------------------------------------------------
    def _from_dataframe(self, df, symbol: str) -> Bars:
        """pandas DataFrame → Bars.

        DataFrame 을 직접 다루는 유일한 곳입니다. 나머지 코드는
        pandas 를 몰라도 됩니다.
        """
        cols = {str(c).strip().lower(): c for c in df.columns}
        need = ["open", "high", "low", "close"]
        missing = [c for c in need if c not in cols]
        if missing:
            raise MarketDataError(
                f"{symbol}: yfinance 응답에 컬럼이 없습니다: {missing}")

        bars: list[Bar] = []
        for idx, row in df.iterrows():
            try:
                ts = int(datetime(idx.year, idx.month, idx.day,
                                  tzinfo=timezone.utc).timestamp())
                bars.append(Bar(
                    ts=ts,
                    open=float(row[cols["open"]]),
                    high=float(row[cols["high"]]),
                    low=float(row[cols["low"]]),
                    close=float(row[cols["close"]]),
                    volume=float(row[cols["volume"]]) if "volume" in cols else 0.0,
                ))
            except (ValueError, TypeError, AttributeError):
                continue

        if not bars:
            raise MarketDataError(f"{symbol}: 변환 가능한 행이 없습니다")

        bars.sort(key=lambda b: b.ts)
        out = Bars(symbol=symbol.upper(), bars=bars, source=self.id,
                   adjusted=self.auto_adjust)
        out.notes.append(
            "auto_adjust=False 로 원주가를 받았습니다. 조정주가는 과거 값이 "
            "나중에 바뀌므로, 그대로 쓰면 백테스트에 미래 정보가 섞입니다."
            if not self.auto_adjust else
            "⚠ auto_adjust=True 입니다. 과거 값이 나중에 변할 수 있어 "
            "Point-in-Time 원칙과 충돌합니다."
        )
        return out

    def health(self) -> dict:
        installed = self.is_installed()
        return {
            "id": self.id,
            "name": self.name,
            "status": "CONNECTED" if installed else "NOT_INSTALLED",
            "requires_key": False,
            "cost": "무료",
            "verified": self.verified,
            "terms_note": self.terms_note,
            "detail": ("설치됨" if installed else
                       "미설치 — 오류가 아닙니다. Stooq/CSV 를 쓰면 됩니다."),
        }
