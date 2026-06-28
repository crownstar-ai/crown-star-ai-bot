# ====================================================================================================
# text_utils.py – Text processing utilities for CrownStar‑Absolute
# Features:
#   - Text cleaning (whitespace, control chars, Unicode normalization)
#   - Smart truncation (by words, sentences, tokens, with ellipsis)
#   - Language detection (multiple backends with fallback)
#   - HTML/XML stripping and markdown cleaning
#   - Text hashing and similarity (shingling, Jaccard)
#   - Sentence splitting and word extraction
#   - Regex utilities for common patterns
# ====================================================================================================

import re
import unicodedata
import hashlib
import string
from typing import List, Tuple, Optional, Dict, Any, Set
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# 1. Text Cleaning
# --------------------------------------------------------------------

def clean_whitespace(text: str, strip_lines: bool = True, normalize_spaces: bool = True) -> str:
    """
    Normalize whitespace in text.
    
    Args:
        text: Input string
        strip_lines: Remove leading/trailing spaces on each line
        normalize_spaces: Collapse multiple spaces into one
    
    Returns:
        Cleaned string
    """
    if not text:
        return ""
    
    # Replace all whitespace sequences with a single space
    if normalize_spaces:
        text = re.sub(r'\s+', ' ', text)
    
    # Strip each line
    if strip_lines:
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
    
    return text.strip()

def remove_control_characters(text: str, keep_newlines: bool = True) -> str:
    """
    Remove control characters (except newline/tab if specified).
    
    Args:
        text: Input string
        keep_newlines: Keep '\\n' and '\\r' characters
    
    Returns:
        Cleaned string
    """
    if keep_newlines:
        # Remove all control chars except newline, carriage return, tab
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    else:
        return re.sub(r'[\x00-\x1f\x7f]', '', text)

def normalize_unicode(text: str, form: str = 'NFKC') -> str:
    """
    Normalize Unicode text to standard form (NFKC, NFD, NFC, NFKD).
    
    Args:
        text: Input string
        form: Unicode normalization form
    
    Returns:
        Normalized string
    """
    return unicodedata.normalize(form, text)

def remove_emojis(text: str) -> str:
    """
    Remove emoji characters from text.
    """
    # Emoji regex pattern (approximate)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric shapes
        "\U0001F800-\U0001F8FF"  # Supplemental arrows
        "\U0001F900-\U0001F9FF"  # Supplemental symbols
        "\U0001FA00-\U0001FA6F"  # Chess symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and pictographs
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub(r'', text)

def clean_text(text: str, 
               lowercase: bool = False,
               remove_punctuation: bool = False,
               remove_numbers: bool = False,
               remove_emojis_flag: bool = False,
               normalize_unicode_flag: bool = True,
               normalize_whitespace: bool = True) -> str:
    """
    Comprehensive text cleaning with multiple options.
    
    Args:
        text: Input string
        lowercase: Convert to lowercase
        remove_punctuation: Strip punctuation characters
        remove_numbers: Strip digits
        remove_emojis_flag: Remove emoji characters
        normalize_unicode_flag: Apply NFKC normalization
        normalize_whitespace: Collapse whitespace
    
    Returns:
        Cleaned string
    """
    if not text:
        return ""
    
    if normalize_unicode_flag:
        text = normalize_unicode(text)
    
    if remove_emojis_flag:
        text = remove_emojis(text)
    
    if remove_punctuation:
        text = text.translate(str.maketrans('', '', string.punctuation))
    
    if remove_numbers:
        text = re.sub(r'\d+', '', text)
    
    if lowercase:
        text = text.lower()
    
    if normalize_whitespace:
        text = clean_whitespace(text)
    
    text = remove_control_characters(text, keep_newlines=True)
    
    return text

# --------------------------------------------------------------------
# 2. Smart Truncation
# --------------------------------------------------------------------

def truncate_by_words(text: str, max_words: int, ellipsis: str = "...") -> str:
    """
    Truncate text by word count, preserving whole words.
    
    Args:
        text: Input string
        max_words: Maximum number of words to keep
        ellipsis: String to append if truncated
    
    Returns:
        Truncated text
    """
    words = text.split()
    if len(words) <= max_words:
        return text
    truncated = ' '.join(words[:max_words])
    if ellipsis:
        truncated += ellipsis
    return truncated

def truncate_by_chars(text: str, max_chars: int, ellipsis: str = "...") -> str:
    """
    Truncate text by character count, trying to break at word boundaries.
    
    Args:
        text: Input string
        max_chars: Maximum characters to keep
        ellipsis: String to append if truncated
    """
    if len(text) <= max_chars:
        return text
    
    # Try to break at last space within limit
    truncated = text[:max_chars]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    
    if ellipsis:
        truncated += ellipsis
    return truncated

def truncate_by_sentences(text: str, max_sentences: int, ellipsis: str = "...") -> str:
    """
    Truncate text by sentence count (using simple regex).
    
    Args:
        text: Input string
        max_sentences: Maximum number of sentences to keep
        ellipsis: String to append if truncated
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if len(sentences) <= max_sentences:
        return text
    truncated = ' '.join(sentences[:max_sentences])
    if ellipsis:
        truncated += ellipsis
    return truncated

def truncate_with_token_estimator(text: str, max_tokens: int, 
                                  tokens_per_word: float = 1.3, ellipsis: str = "...") -> str:
    """
    Approximate truncation by token count (useful for LLM context limits).
    
    Args:
        text: Input string
        max_tokens: Maximum estimated tokens
        tokens_per_word: Average tokens per word (1.3 for English)
        ellipsis: String to append if truncated
    """
    words = text.split()
    approx_tokens = len(words) * tokens_per_word
    if approx_tokens <= max_tokens:
        return text
    # Keep proportionally fewer words
    keep_ratio = max_tokens / approx_tokens
    keep_words = max(1, int(len(words) * keep_ratio * 0.9))
    truncated = ' '.join(words[:keep_words])
    if ellipsis:
        truncated += ellipsis
    return truncated

# --------------------------------------------------------------------
# 3. Language Detection
# --------------------------------------------------------------------

def detect_language(text: str, method: str = "auto") -> Tuple[str, float]:
    """
    Detect language of text using available libraries.
    
    Args:
        text: Input text (at least 20 characters for reliable detection)
        method: "auto", "langdetect", "cld3", "simple"
    
    Returns:
        Tuple of (language_code, confidence)
    """
    if not text or len(text) < 10:
        return ("en", 0.5)
    
    # Try langdetect first
    if method in ("auto", "langdetect"):
        try:
            from langdetect import detect_langs
            results = detect_langs(text)
            if results:
                best = results[0]
                return (best.lang, best.prob)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"langdetect failed: {e}")
    
    # Try cld3 (Compact Language Detector)
    if method in ("auto", "cld3"):
        try:
            import cld3
            result = cld3.get_language(text)
            if result and result.is_reliable:
                return (result.language, result.probability)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"cld3 failed: {e}")
    
    # Fallback: simple heuristic (character frequency)
    return _simple_language_detection(text)

def _simple_language_detection(text: str) -> Tuple[str, float]:
    """
    Very basic language detection using common character patterns.
    Returns (language_code, confidence).
    """
    text_lower = text.lower()
    # Common English words
    english_markers = [' the ', ' and ', ' of ', ' to ', ' is ', ' in ']
    english_score = sum(1 for m in english_markers if m in text_lower) / len(english_markers)
    
    # Common French words
    french_markers = [' le ', ' la ', ' de ', ' et ', ' est ', ' dans ']
    french_score = sum(1 for m in french_markers if m in text_lower) / len(french_markers)
    
    # Common German words
    german_markers = [' der ', ' die ', ' und ', ' ist ', ' zu ', ' auf ']
    german_score = sum(1 for m in german_markers if m in text_lower) / len(german_markers)
    
    # Common Spanish words
    spanish_markers = [' el ', ' la ', ' de ', ' y ', ' es ', ' en ']
    spanish_score = sum(1 for m in spanish_markers if m in text_lower) / len(spanish_markers)
    
    scores = {
        'en': english_score,
        'fr': french_score,
        'de': german_score,
        'es': spanish_score,
    }
    best_lang = max(scores, key=scores.get)
    confidence = scores[best_lang] * 0.7 + 0.2  # scale to [0.2, 0.9]
    return (best_lang, confidence)

def is_english(text: str, threshold: float = 0.6) -> bool:
    """Quick check if text is likely English."""
    lang, conf = detect_language(text)
    return lang == 'en' and conf >= threshold

# --------------------------------------------------------------------
# 4. HTML / Markdown Stripping
# --------------------------------------------------------------------

def strip_html(text: str, keep_links: bool = False) -> str:
    """
    Remove HTML tags from text.
    
    Args:
        text: HTML string
        keep_links: Keep <a href="..."> link text instead of removing entirely
    
    Returns:
        Plain text
    """
    if not text:
        return ""
    
    # Remove script and style elements
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    if keep_links:
        # Replace <a> with its href text
        text = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'\2 (\1)', text, flags=re.IGNORECASE)
    
    # Remove all other tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Decode HTML entities
    import html
    text = html.unescape(text)
    
    return clean_whitespace(text)

def strip_markdown(text: str) -> str:
    """
    Remove common Markdown formatting.
    """
    if not text:
        return ""
    
    # Remove headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)
    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove links (keep text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove images
    text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove list markers
    text = re.sub(r'^(\s*[-*+]|\d+\.)\s+', '', text, flags=re.MULTILINE)
    # Remove blockquotes
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    
    return clean_whitespace(text)

# --------------------------------------------------------------------
# 5. Text Hashing and Similarity
# --------------------------------------------------------------------

def text_hash(text: str, algorithm: str = 'md5') -> str:
    """
    Compute hash of text (useful for deduplication).
    
    Args:
        text: Input string
        algorithm: 'md5', 'sha1', 'sha256'
    
    Returns:
        Hexadecimal hash string
    """
    encoded = text.encode('utf-8')
    if algorithm == 'md5':
        return hashlib.md5(encoded).hexdigest()
    elif algorithm == 'sha1':
        return hashlib.sha1(encoded).hexdigest()
    else:
        return hashlib.sha256(encoded).hexdigest()

def shingle(text: str, k: int = 3) -> Set[str]:
    """
    Convert text into set of k-shingles (character n-grams).
    
    Args:
        text: Input string (cleaned)
        k: Shingle length (characters)
    
    Returns:
        Set of shingles
    """
    text = clean_whitespace(text)
    if len(text) < k:
        return {text}
    return {text[i:i+k] for i in range(len(text) - k + 1)}

def jaccard_similarity(text1: str, text2: str, k: int = 3) -> float:
    """
    Compute Jaccard similarity between two texts based on k-shingles.
    """
    set1 = shingle(text1, k)
    set2 = shingle(text2, k)
    if not set1 and not set2:
        return 1.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0

# --------------------------------------------------------------------
# 6. Sentence Splitting and Word Extraction
# --------------------------------------------------------------------

def split_sentences(text: str) -> List[str]:
    """
    Split text into sentences using punctuation and capitalisation heuristics.
    """
    # Simple but robust: split on .!? followed by space or end of string
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.strip())
    return sentences

def extract_words(text: str, min_length: int = 1, stopwords: Set[str] = None) -> List[str]:
    """
    Extract words from text, optionally filtering by length and stopwords.
    
    Args:
        text: Input string
        min_length: Minimum word length
        stopwords: Set of words to exclude
    
    Returns:
        List of words
    """
    words = re.findall(r'\b[a-zA-Z]{' + str(min_length) + r',}\b', text.lower())
    if stopwords:
        words = [w for w in words if w not in stopwords]
    return words

# --------------------------------------------------------------------
# 7. Regex Utilities for Common Patterns
# --------------------------------------------------------------------

def extract_urls(text: str) -> List[str]:
    """Extract all URLs from text."""
    pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?::\d+)?(?:/[-\w%!?/=&;:.@#$~+*]*)?'
    return re.findall(pattern, text)

def extract_emails(text: str) -> List[str]:
    """Extract email addresses from text."""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(pattern, text)

def extract_dates(text: str) -> List[str]:
    """Extract date patterns (YYYY-MM-DD, DD/MM/YYYY, etc.)"""
    patterns = [
        r'\b\d{4}-\d{2}-\d{2}\b',           # 2024-01-15
        r'\b\d{2}/\d{2}/\d{4}\b',           # 15/01/2024
        r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b',  # 15 Jan 2024
    ]
    dates = []
    for pattern in patterns:
        dates.extend(re.findall(pattern, text))
    return list(set(dates))

def extract_phone_numbers(text: str) -> List[str]:
    """Extract phone number patterns (simple)."""
    pattern = r'\b(?:\+?[\d\s()-]{8,20})\b'
    return re.findall(pattern, text)

def mask_pii(text: str, replace_with: str = "[REDACTED]") -> str:
    """
    Mask personally identifiable information (emails, phone numbers, etc.)
    """
    # Mask emails
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', replace_with, text)
    # Mask phone numbers (simple)
    text = re.sub(r'\b(?:\+?[\d\s()-]{8,20})\b', replace_with, text)
    # Mask IP addresses (IPv4)
    text = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', replace_with, text)
    return text

# --------------------------------------------------------------------
# 8. Truncation for LLM Context
# --------------------------------------------------------------------

def truncate_for_context(text: str, max_chars: int = 4000, 
                         preserve_ends: bool = True,
                         head_ratio: float = 0.7) -> str:
    """
    Truncate text for LLM context window, preserving beginning and end.
    
    Args:
        text: Input string
        max_chars: Maximum characters allowed
        preserve_ends: Keep head and tail, remove middle
        head_ratio: Proportion of text to keep from beginning (rest from end)
    
    Returns:
        Truncated text
    """
    if len(text) <= max_chars:
        return text
    
    if not preserve_ends:
        return truncate_by_chars(text, max_chars)
    
    head_len = int(max_chars * head_ratio)
    tail_len = max_chars - head_len - 3  # -3 for "..."
    
    head = text[:head_len]
    tail = text[-tail_len:] if tail_len > 0 else ""
    
    return f"{head}...{tail}"

# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
# Clean text
raw = "  Hello   world!  \n\n  This is a test.  "
clean = clean_text(raw, lowercase=True, normalize_whitespace=True)
print(clean)

# Detect language
lang, conf = detect_language("This is an English sentence.")
print(f"Language: {lang}, confidence: {conf}")

# Truncate for context
long_text = "..." * 1000
short = truncate_for_context(long_text, max_chars=200)
print(short)

# Extract URLs
urls = extract_urls("Check https://crownstar.ai and http://example.com")
print(urls)
"""

# ====================================================================================================
# END OF text_utils.py
# ====================================================================================================
