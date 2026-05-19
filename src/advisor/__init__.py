"""CoinDCX Futures advisor signal pipeline (SOP-compliant)."""

from src.advisor.schemas import AdvisorSignal

__all__ = ["AdvisorProcessor", "AdvisorSignal"]


def __getattr__(name: str):
    if name == "AdvisorProcessor":
        from src.advisor.processor import AdvisorProcessor
        return AdvisorProcessor
    raise AttributeError(name)
