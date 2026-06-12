import asyncio
import sys
import logging
import os

# Add the project root to the python path so imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analysis.learning_engine import WeightOptimizer

logging.basicConfig(level=logging.INFO)

async def main():
    optimizer = WeightOptimizer()
    print("Starting Reinforcement Learning Weight Tuning...")
    await optimizer.run_optimization(days=30, include_backtest_log=True)
    print("Optimization finished successfully.")

if __name__ == "__main__":
    asyncio.run(main())
