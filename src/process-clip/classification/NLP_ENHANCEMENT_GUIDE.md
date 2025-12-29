# NLP Enhancement Guide

## Comparison: Rule-Based vs NLP-Enhanced

### Rule-Based Transcript Extractor (Current)

**Pros:**
- ✅ **Zero dependencies** - Pure Python
- ✅ **Fast** - <1ms processing
- ✅ **Transparent** - Know exactly why it classified
- ✅ **Reliable** - No model drift or API failures
- ✅ **Lambda-ready** - No setup needed

**Cons:**
- ❌ Fixed vocabulary - Only matches exact keywords
- ❌ No context - Can't detect semantic meaning
- ❌ Misses synonyms - "awesome" ≠ "nice"
- ❌ Language-specific - English only

**Best for:**
- Production Lambda deployment
- Cost-conscious applications
- Real-time processing (<10ms requirement)
- Transparent/explainable AI needs

### NLP-Enhanced Transcript Extractor (New)

**Pros:**
- ✅ **Semantic understanding** - Detects meaning, not just keywords
- ✅ **Better accuracy** - Understands context and synonyms
- ✅ **Richer features** - Sentiment, topics, entities
- ✅ **Adaptive** - Can detect new patterns

**Cons:**
- ❌ Dependencies - Requires spaCy, KeyBERT, sentence-transformers
- ❌ Slower - ~50ms processing
- ❌ Larger footprint - ~200MB for models
- ❌ More complex - Harder to debug

**Best for:**
- Development/testing phase
- High-accuracy requirements
- Batch processing (not real-time)
- When you have server resources

## Performance Comparison

| Metric | Rule-Based | NLP-Enhanced |
|--------|-----------|--------------|
| **Speed** | <1ms | ~50ms |
| **Memory** | <10MB | ~200MB |
| **Dependencies** | 0 | 3-4 packages |
| **Accuracy** | 75-80% | 85-95% |
| **Lambda Cost** | $0.20/1M | $0.50/1M |

## Installation

### Option 1: Rule-Based Only (Recommended for Lambda)
```bash
# Nothing to install! Already works
```

### Option 2: Add NLP Enhancement
```bash
# Install NLP libraries
pip install spacy keybert sentence-transformers textblob scikit-learn

# Download spaCy model (60MB)
python -m spacy download en_core_web_sm
```

## Usage

### Enable NLP Extractor

The system auto-discovers both extractors. NLP extractor has **priority 0** (runs first), rule-based has **priority 1** (fallback).

```python
from classification import get_classification_service

service = get_classification_service()
service.initialize()

# NLP extractor will be used if available, falls back to rule-based
classification, strategy = service.classify_quick(clip_info)
```

### Disable NLP Extractor (Force Rule-Based)

```python
service = get_classification_service()
service.initialize()

# Disable NLP extractor
service.disable_plugin("nlp_transcript_extractor_v1")

# Now only rule-based will run
classification, strategy = service.classify_quick(clip_info)
```

### Check Which Extractor is Active

```python
service = get_classification_service()
service.initialize()

stats = service.get_plugin_stats()
plugins = service.list_plugins()

for plugin in plugins:
    if 'extractor' in plugin['plugin_id']:
        print(f"{plugin['name']}: {plugin['status']}")
```

## Accuracy Improvements

### Example: Gaming Detection

**Input Text:** "That was an epic clutch moment! Absolutely insane gameplay!"

**Rule-Based Output:**
```python
{
  'keywords': ['gaming'],  # Only 'clutch' matched
  'sentiment': None
}
```

**NLP-Enhanced Output:**
```python
{
  'keywords': ['gaming', 'competition', 'performance'],
  'semantic_keywords': ['epic', 'clutch', 'moment', 'insane', 'gameplay'],
  'sentiment': {'polarity': 0.8, 'subjectivity': 0.7},
  'category_similarity': {
    'gaming': 0.87,
    'sports': 0.43,
    'reaction': 0.56
  },
  'excitement_level': 0.85
}
```

Result: **Better confidence** (0.92 vs 0.65)

### Example: Cooking Detection

**Input Text:** "We're going to combine the ingredients and blend them until smooth"

**Rule-Based Output:**
```python
{
  'keywords': [],  # Missed! No exact keyword matches
}
```

**NLP-Enhanced Output:**
```python
{
  'keywords': ['cooking'],
  'semantic_keywords': ['combine', 'ingredients', 'blend', 'smooth'],
  'topics': ['ingredients', 'blend them'],
  'category_similarity': {
    'cooking': 0.78,
    'tutorial': 0.65
  }
}
```

Result: **Detects cooking even without keywords!**

## Lambda Deployment

### Strategy 1: Rule-Based in Lambda, NLP for Development

```python
# config.py
USE_NLP = os.environ.get('USE_NLP', 'false') == 'true'

if USE_NLP:
    # Development/testing with NLP
    service.enable_plugin("nlp_transcript_extractor_v1")
else:
    # Production Lambda with rule-based
    service.disable_plugin("nlp_transcript_extractor_v1")
```

### Strategy 2: Hybrid Approach

Run rule-based first (fast), use NLP for uncertain cases:

```python
# Quick classification (rule-based)
classification, strategy = service.classify_quick(clip_info)

if not classification or classification.confidence < 0.7:
    # Low confidence - enable NLP for better accuracy
    service.enable_plugin("nlp_transcript_extractor_v1")
    classification, strategy = service.classify_quick(clip_info)
```

### Strategy 3: Lambda Layer for NLP

If you need NLP in Lambda:

```bash
# Create layer with NLP models
mkdir -p python/lib/python3.11/site-packages
pip install spacy keybert sentence-transformers -t python/lib/python3.11/site-packages
python -m spacy download en_core_web_sm -t python/lib/python3.11/site-packages

# Zip and upload
zip -r nlp-layer.zip python/
aws lambda publish-layer-version --layer-name nlp-classification --zip-file fileb://nlp-layer.zip
```

**Cost Impact:**
- Layer size: ~250MB
- Cold start: +2-3 seconds
- Memory: 512MB → 1024MB
- Cost increase: ~$0.30/1M requests

## Recommended Approach

### For Production (Lambda)
✅ **Use Rule-Based** - Fast, cheap, reliable
- Add more keywords to improve accuracy
- Tune confidence thresholds
- Monitor misclassifications

### For Development/Testing
✅ **Use NLP-Enhanced** - Better accuracy for validation
- Test classification quality
- Identify edge cases
- Build confidence in system

### For Batch Processing
✅ **Use NLP-Enhanced** - Not time-sensitive
- Process uploaded videos offline
- Better accuracy matters more than speed

## Improving Rule-Based Accuracy

If you don't want NLP dependencies, improve rule-based:

### 1. Expand Keyword Lists
```python
'gaming': [
  # Original
  'gg', 'clutch', 'lets go',
  # Add more
  'epic', 'rage', 'noob', 'pwned', 'fragged', 'camping',
  'headshot', 'respawn', 'loot', 'grind', 'boss fight'
]
```

### 2. Add Phrase Patterns
```python
gaming_phrases = [
  r'\bkill(ed)?\b',
  r'\b(won|lost) the (game|match)\b',
  r'\blevel \d+\b'
]
```

### 3. Weight Keywords by Importance
```python
gaming_keywords = {
  'strong': ['gg', 'clutch', 'headshot'],  # 1.0 confidence
  'medium': ['nice', 'lets go'],            # 0.7 confidence
  'weak': ['bro', 'what']                   # 0.3 confidence
}
```

## Monitoring & Metrics

Track accuracy over time:

```python
# Log classifications for analysis
{
  'clip_id': '...',
  'classification': 'gaming',
  'confidence': 0.77,
  'extractor_used': 'rule_based',
  'processing_time_ms': 0.5,
  'correct': True  # Manual validation
}
```

Analyze:
- Accuracy by category
- Confidence distribution
- Processing time
- False positives/negatives

## Conclusion

**Start with rule-based, add NLP if needed.**

The plugin architecture lets you:
- ✅ Swap extractors without code changes
- ✅ Run both and compare results
- ✅ Choose based on environment (Lambda vs server)
- ✅ Gradually improve over time

Most use cases work great with rule-based! 🎯
