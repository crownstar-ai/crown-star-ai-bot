# ====================================================================================================
# sentiment_plugin.py – CrownStar‑Absolute Example Sentiment Analysis Plugin
# Demonstrates:
#   - Plugin metadata (name, version, author, dependencies)
#   - Pre‑answer hook (detect sentiment of user query, optionally respond directly)
#   - Post‑answer hook (add sentiment label to responses)
#   - Custom slash command (/sentiment)
#   - Plugin configuration (enable/disable sentiment labeling, threshold)
#   - Logging and integration with CrownStar core
# ====================================================================================================

import re
import logging
from typing import Optional, Tuple

# Try to import a sentiment library, fallback to simple keyword matching
try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False
    # Simple keyword‑based sentiment (very basic fallback)
    POSITIVE_WORDS = {'good', 'great', 'awesome', 'excellent', 'wonderful', 'amazing', 'love',
                      'happy', 'joy', 'positive', 'fantastic', 'brilliant', 'perfect'}
    NEGATIVE_WORDS = {'bad', 'terrible', 'awful', 'horrible', 'sad', 'angry', 'hate', 'dislike',
                      'negative', 'frustrated', 'annoying', 'poor', 'wrong', 'error', 'fail'}

from crownstar_plugin import CrownStarPlugin

# Plugin metadata (read by plugin manager)
__plugin_name__ = "Sentiment Analyzer"
__plugin_version__ = "1.0.0"
__plugin_author__ = "CrownStar Labs"
__plugin_description__ = "Analyzes sentiment of user queries and AI responses, adds sentiment labels."
__plugin_dependencies__ = []  # textblob is optional; plugin works without it
__plugin_enabled_by_default__ = True
__plugin_api_version__ = 1

class SentimentPlugin(CrownStarPlugin):
    """
    Sentiment analysis plugin for CrownStar‑Absolute.
    Adds a '/sentiment' command and optionally labels AI responses with sentiment.
    """
    
    def __init__(self, core, plugin_info):
        super().__init__(core, plugin_info)
        self._sentiment_threshold = self.get_config("threshold", 0.2)
        self._add_sentiment_label = self.get_config("add_sentiment_label", True)
        self._respond_on_negative = self.get_config("respond_on_negative", False)
        self._negative_response_template = self.get_config(
            "negative_response_template",
            "I notice you seem frustrated. How can I help improve your experience?"
        )
    
    def on_load(self):
        self.logger.info("Sentiment plugin loaded")
        # Register slash command
        self.register_command("sentiment", self.cmd_sentiment)
    
    def on_enable(self):
        self.logger.info("Sentiment plugin enabled")
        # Reload config from core
        self._sentiment_threshold = self.get_config("threshold", 0.2)
        self._add_sentiment_label = self.get_config("add_sentiment_label", True)
        self._respond_on_negative = self.get_config("respond_on_negative", False)
    
    def on_disable(self):
        self.logger.info("Sentiment plugin disabled")
    
    def _analyze_sentiment(self, text: str) -> Tuple[str, float]:
        """
        Analyze sentiment of text.
        Returns (polarity_label, polarity_score) where polarity_score is between -1 (negative) and +1 (positive).
        """
        if not text:
            return ("neutral", 0.0)
        
        if HAS_TEXTBLOB:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            if polarity > self._sentiment_threshold:
                label = "positive"
            elif polarity < -self._sentiment_threshold:
                label = "negative"
            else:
                label = "neutral"
            return (label, polarity)
        else:
            # Simple keyword matching fallback
            words = set(re.findall(r'\b\w+\b', text.lower()))
            pos_count = len(words & POSITIVE_WORDS)
            neg_count = len(words & NEGATIVE_WORDS)
            if pos_count > neg_count:
                return ("positive", min(1.0, pos_count / (pos_count + neg_count + 1)))
            elif neg_count > pos_count:
                return ("negative", -min(1.0, neg_count / (pos_count + neg_count + 1)))
            else:
                return ("neutral", 0.0)
    
    async def pre_answer(self, query: str, tier: str) -> Optional[str]:
        """
        Check sentiment of user query. If very negative and respond_on_negative is True,
        return a canned empathetic response instead of the normal AI answer.
        """
        if not self._respond_on_negative:
            return None
        
        sentiment, polarity = self._analyze_sentiment(query)
        if sentiment == "negative" and polarity < -0.5:
            self.logger.info(f"Negative query detected (score {polarity:.2f}) – returning empathetic response")
            return self._negative_response_template
        return None
    
    async def post_answer(self, query: str, response: str, tier: str) -> str:
        """
        Add sentiment label to AI response (if enabled).
        """
        if not self._add_sentiment_label:
            return response
        
        # Analyze sentiment of the response itself
        sentiment, polarity = self._analyze_sentiment(response)
        if sentiment == "neutral":
            return response
        
        # Choose an emoji based on sentiment
        emoji = "😊" if sentiment == "positive" else "😞" if sentiment == "negative" else "😐"
        
        # Append a small sentiment indicator (avoid adding if already present)
        label = f"\n\n{emoji} *Sentiment: {sentiment.capitalize()}*"
        # Don't duplicate if already added
        if label not in response:
            return response + label
        return response
    
    async def cmd_sentiment(self, args: str) -> str:
        """
        Slash command: /sentiment [text]
        Analyzes sentiment of the provided text (or the last user query if no text).
        """
        if not args:
            # Use last user message from conversation memory
            last_user_msg = None
            if hasattr(self.core, 'shell') and self.core.shell:
                for msg in reversed(self.core.shell.state.memory):
                    if msg.get("role") == "user":
                        last_user_msg = msg.get("content", "")
                        break
            if not last_user_msg:
                return "No previous user message found. Usage: `/sentiment <text>`"
            text = last_user_msg
        else:
            text = args
        
        sentiment, polarity = self._analyze_sentiment(text)
        # Build a detailed response
        if HAS_TEXTBLOB:
            method = "TextBlob"
        else:
            method = "keyword (fallback)"
        return (f"**Sentiment Analysis** (using {method})\n"
                f"Text: {text[:200]}\n"
                f"Sentiment: {sentiment.upper()}\n"
                f"Polarity score: {polarity:.3f}\n"
                f"Interpretation: " + (
                    "Strongly positive 😊" if polarity > 0.7 else
                    "Positive 🙂" if polarity > 0.2 else
                    "Neutral 😐" if abs(polarity) <= 0.2 else
                    "Negative 😞" if polarity < -0.2 else
                    "Strongly negative 😫" if polarity < -0.7 else "Mixed"
                ))
    
    # The following methods demonstrate optional plugin functionality
    def on_startup(self):
        """Called when CrownStar core starts up (after initialisation)."""
        self.logger.info("Sentiment plugin startup – ready to analyze emotions")
    
    def on_shutdown(self):
        """Called when CrownStar core shuts down."""
        self.logger.info("Sentiment plugin shutting down – goodbye!")

# --------------------------------------------------------------------
# Additional: if run as standalone script (testing), print plugin info
# --------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Plugin: {__plugin_name__} v{__plugin_version__}")
    print(f"Author: {__plugin_author__}")
    print(f"Description: {__plugin_description__}")
    print(f"Dependencies: {__plugin_dependencies__}")
    print("This plugin requires CrownStar‑Absolute with plugin manager support.")
    print("\nTo install: place this file in the 'plugins/' directory and enable it.")
    print("Example usage after enabling: /sentiment I love CrownStar!")
