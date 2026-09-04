"""가져온 시세를 시스템 안으로 들여보내는 통로.

★ 여기가 Point-in-Time 규칙이 실제로 강제되는 지점입니다.

    시세 봉 하나가 '사실'이 될 때 네 개의 시간이 붙습니다.

        event_time     그 거래일 (봉의 날짜)
        published_time 그 값이 세상에 공개된 시각
                       ★ 일봉 종가는 **장 마감 후**에 확정됩니다.
                         봉의 날짜 00:00 로 두면, 그날 아침에 이미
                         그날 종가를 아는 것이 되어 버립니다.
                         그래서 마감 시각을 더합니다.
        received_time  우리가 받은 시각
        effective_time = published_time

    이 한 줄의 차이가 백테스트 수익률을 환상적으로 만들었다가
    실전에서 전부 잃게 만드는 차이입니다.
"""

from __future__ import annotations

from typing import Sequence

# 거래소별 정규장 마감 시각 (UTC 기준 초). 서머타임은 무시하고
# **보수적으로 늦게** 잡습니다. 늦게 잡을수록 정보를 늦게 보므로 안전합니다.
CLOSE_OFFSET_SECONDS = {
    "XNYS": 21 * 3600,      # 미 동부 16:00 ≈ UTC 21:00 (EST 기준)
    "XKRX": 6 * 3600 + 1800,  # 한국 15:30 = UTC 06:30
}
DEFAULT_CLOSE_OFFSET = 23 * 3600      # 모르면 그날 끝으로 (가장 보수적)


def publish_time_for(ts: int, exchange: str | None) -> int:
    """일봉이 '공개된' 시각. 봉 날짜 + 장 마감."""
    return ts + CLOSE_OFFSET_SECONDS.get((exchange or "").upper(),
                                         DEFAULT_CLOSE_OFFSET)


def to_ohlcv(bars) -> "object":
    """market_data.Bars → chart_skills.OHLCV (학습·백테스트가 쓰는 타입)."""
    from packages.chart_skills.series import Candle, OHLCV

    return OHLCV([
        Candle(ts=b.ts, open=b.open, high=b.high, low=b.low,
               close=b.close, volume=b.volume)
        for b in bars
    ])


def ingest_bars(bars, store=None, pit_store=None,
                exchange: str | None = "XNYS",
                source_id: str = "") -> dict:
    """가져온 봉을 저장소와 PIT Store 에 넣습니다.

    반환값에는 **무엇을 몇 개 넣었는지**가 들어 있어, 화면에서
    "실제 데이터 N건" 이라고 정직하게 표시할 수 있습니다.
    """
    report = {
        "symbol": bars.symbol,
        "bars": len(bars),
        "stored_bars": 0,
        "pit_records": 0,
        "exchange": exchange,
        "adjusted": bars.adjusted,
        "source": bars.source,
        "errors": [],
        "pit_note": (
            "일봉 종가의 published_time 은 '봉 날짜 + 장 마감 시각' 입니다. "
            "그날 아침에는 그날 종가를 볼 수 없습니다."
        ),
    }

    if store is not None:
        try:
            report["stored_bars"] = store.put_bars(
                bars.symbol, bars.to_dicts(),
                source=bars.source, adjusted=bars.adjusted,
            )
        except Exception as exc:
            report["errors"].append(f"캔들 저장 실패: {exc}")

    if pit_store is not None:
        try:
            from packages.pit_store.store import Record

            n = 0
            for b in bars:
                pit_store.put_fact(Record(
                    key=f"{bars.symbol}:close",
                    value=b.close,
                    event_time=b.ts,
                    published_time=publish_time_for(b.ts, exchange),
                    received_time=bars.fetched_at,
                    effective_time=publish_time_for(b.ts, exchange),
                    source_id=source_id or bars.source,
                    confidence=1.0,
                ))
                n += 1
            report["pit_records"] = n
        except Exception as exc:
            report["errors"].append(f"PIT 적재 실패: {exc}")

    return report
