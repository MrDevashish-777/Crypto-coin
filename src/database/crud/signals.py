# CRUD Operations - Signals
# Database operations for trading signals

from sqlalchemy.orm import Session
from src.database.models import Signal
from datetime import datetime, timedelta


class SignalCRUD:
    """CRUD operations for signals"""

    @staticmethod
    def create_signal(db: Session, signal_data: dict) -> Signal:
        """Create a new signal record"""
        signal = Signal(**signal_data)
        db.add(signal)
        db.commit()
        db.refresh(signal)
        return signal

    @staticmethod
    def get_signal(db: Session, signal_id: int) -> Signal:
        """Get signal by ID"""
        return db.query(Signal).filter(Signal.id == signal_id).first()

    @staticmethod
    def get_signals_by_symbol(db: Session, symbol: str, limit: int = 100) -> list:
        """Get signals for a symbol"""
        return db.query(Signal).filter(
            Signal.symbol == symbol
        ).order_by(Signal.generated_at.desc()).limit(limit).all()

    @staticmethod
    def get_recent_signals(db: Session, hours: int = 24, limit: int = 100) -> list:
        """Get signals from last N hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return db.query(Signal).filter(
            Signal.generated_at >= cutoff_time
        ).order_by(Signal.generated_at.desc()).limit(limit).all()

    @staticmethod
    def get_signals_by_strategy(db: Session, strategy: str, limit: int = 100) -> list:
        """Get signals from specific strategy"""
        return db.query(Signal).filter(
            Signal.strategy_name == strategy
        ).order_by(Signal.generated_at.desc()).limit(limit).all()
