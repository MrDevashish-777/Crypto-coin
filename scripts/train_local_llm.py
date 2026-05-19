"""
Script to train the local Transformer model using collected samples.
"""

import logging
from src.database.db import SessionLocal
from src.database.models import LLMTrainingSample
from src.llm.transformer_agent import TransformerTrainer
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_training():
    """Fetch samples from DB and train the model"""
    db = SessionLocal()
    try:
        samples = db.query(LLMTrainingSample).all()
        
        if not samples:
            logger.warning("No training samples found in database. Start collecting data first!")
            return
            
        logger.info(f"Found {len(samples)} samples. Preparing for training...")
        
        training_data = [
            {"input": sample.input_text, "label": sample.label}
            for sample in samples
        ]
        
        trainer = TransformerTrainer()
        trainer.train(training_data, epochs=5)
        
        logger.info("✓ Training completed successfully")
        
    except Exception as e:
        logger.error(f"✗ Training failed: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    run_training()
