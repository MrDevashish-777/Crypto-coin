"""
Transformer-based Agent for Crypto Signal Generation
Dedicated local model for crypto analysis and signal confirmation.
"""

import os
import json
import logging
import torch
from typing import Dict, Any, List, Optional
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    pipeline,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding
)
from datasets import Dataset
from src.llm.agent import LLMAgent

logger = logging.getLogger(__name__)

class TransformerAgent(LLMAgent):
    """
    Local Transformer-based agent for crypto signal generation.
    Uses a fine-tuned model (e.g., DistilBERT or RoBERTa) to classify market conditions.
    """

    def __init__(
        self, 
        model_path: str = "models/crypto-transformer",
        default_model: str = "distilbert-base-uncased",
        device: str = "auto"
    ):
        """Initialize the Transformer agent"""
        self.model_path = model_path
        self.default_model = default_model
        
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        self._load_model()
        logger.info(f"TransformerAgent initialized on {self.device}")

    def _load_model(self):
        """Load the model and tokenizer from disk or default"""
        try:
            if os.path.exists(self.model_path):
                logger.info(f"Loading local model from {self.model_path}")
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
                self.model = AutoModelForSequenceClassification.from_pretrained(self.model_path)
            else:
                logger.warning(f"Local model not found at {self.model_path}. Using default {self.default_model}")
                self.tokenizer = AutoTokenizer.from_pretrained(self.default_model)
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    self.default_model, 
                    num_labels=3  # Bearish, Neutral, Bullish
                )
            
            self.model.to(self.device)
            self.classifier = pipeline(
                "text-classification", 
                model=self.model, 
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" else -1
            )
        except Exception as e:
            logger.error(f"Failed to load Transformer model: {str(e)}")
            raise

    def _prepare_input(self, market_data: Dict[str, Any], context: str = "") -> str:
        """Convert market data and context into a string for the transformer"""
        input_text = f"Symbol: {market_data.get('symbol', 'N/A')} | "
        input_text += f"Price: {market_data.get('price', 'N/A')} | "
        input_text += f"RSI: {market_data.get('rsi', 'N/A')} | "
        input_text += f"MACD: {market_data.get('macd', 'N/A')} | "
        input_text += f"Change: {market_data.get('change_24h', 'N/A')}% | "
        input_text += f"Context: {context[:500]}"
        return input_text

    async def analyze_market(self, market_data: Dict[str, Any], context: str = "") -> Dict[str, Any]:
        """Analyze market data using the local transformer"""
        try:
            input_text = self._prepare_input(market_data, context)
            results = self.classifier(input_text)
            
            if not results:
                return {"sentiment": "neutral", "confidence": 0.5, "reasoning": "Model returned no results"}
            
            # Map labels to sentiments
            label_map = {"LABEL_0": "bearish", "LABEL_1": "neutral", "LABEL_2": "bullish"}
            result = results[0]
            sentiment = label_map.get(result['label'], "neutral")
            confidence = result['score']
            
            return {
                "sentiment": sentiment,
                "confidence": confidence,
                "risk_level": "medium", # Default for now
                "reasoning": f"Local Transformer analysis: {sentiment} with {confidence:.2f} confidence."
            }
        except Exception as e:
            logger.error(f"Transformer analysis failed: {str(e)}")
            return {"sentiment": "neutral", "confidence": 0.0, "error": str(e)}

    async def generate_signal_confidence(
        self,
        symbol: str,
        indicators: Dict[str, Any],
        price_action: str,
        context: str = ""
    ) -> float:
        """Generate confidence score for signal"""
        market_data = {"symbol": symbol, **indicators, "price_action": price_action}
        analysis = await self.analyze_market(market_data, context)
        return float(analysis.get("confidence", 0.0))

    async def analyze_news_sentiment(self, news_text: str) -> Dict[str, Any]:
        """Analyze news sentiment with the transformer"""
        try:
            results = self.classifier(f"ANALYZE SENTIMENT: {news_text}")
            if not results:
                return {"sentiment": "neutral", "confidence": 0.5, "reasoning": "Model returned no results"}
            
            label_map = {"LABEL_0": "bearish", "LABEL_1": "neutral", "LABEL_2": "bullish"}
            result = results[0]
            sentiment = label_map.get(result['label'], "neutral")
            confidence = result['score']
            
            return {
                "sentiment": sentiment,
                "confidence": confidence,
                "reasoning": f"Local Transformer analysis: {sentiment} with {confidence:.2f} confidence."
            }
        except Exception as e:
            logger.error(f"Transformer news analysis failed: {str(e)}")
            return {"sentiment": "neutral", "confidence": 0.0, "reasoning": str(e)}

class TransformerTrainer:
    """
    Handles training/fine-tuning of the TransformerAgent model.
    Implements distillation from larger LLMs (OpenAI/Anthropic).
    """
    
    def __init__(self, base_model: str = "distilbert-base-uncased", output_dir: str = "models/crypto-transformer"):
        self.base_model = base_model
        self.output_dir = output_dir
        self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        
    def prepare_dataset(self, training_data: List[Dict[str, Any]]):
        """
        Convert raw LLM outputs and market data into a Hugging Face Dataset.
        training_data format: [{"input": "...", "label": 0/1/2}]
        """
        inputs = [item['input'] for item in training_data]
        labels = [item['label'] for item in training_data]
        
        dataset = Dataset.from_dict({"text": inputs, "label": labels})
        
        def tokenize_function(examples):
            return self.tokenizer(examples["text"], padding="max_length", truncation=True)
            
        tokenized_dataset = dataset.map(tokenize_function, batched=True)
        return tokenized_dataset

    def train(self, training_data: List[Dict[str, Any]], epochs: int = 3):
        """Train/Fine-tune the model"""
        logger.info(f"Starting training on {len(training_data)} samples...")
        
        tokenized_dataset = self.prepare_dataset(training_data)
        
        model = AutoModelForSequenceClassification.from_pretrained(
            self.base_model, 
            num_labels=3
        )
        
        training_args = TrainingArguments(
            output_dir="./results",
            learning_rate=2e-5,
            per_device_train_batch_size=16,
            num_train_epochs=epochs,
            weight_decay=0.01,
            logging_dir="./logs",
            logging_steps=10,
        )
        
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_dataset,
            tokenizer=self.tokenizer,
            data_collator=DataCollatorWithPadding(tokenizer=self.tokenizer),
        )
        
        trainer.train()
        
        # Save the fine-tuned model
        os.makedirs(self.output_dir, exist_ok=True)
        model.save_pretrained(self.output_dir)
        self.tokenizer.save_pretrained(self.output_dir)
        logger.info(f"Model saved to {self.output_dir}")
