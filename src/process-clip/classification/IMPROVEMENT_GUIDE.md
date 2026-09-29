# Classification System Improvement Guide

This guide shows how to improve classification accuracy from 65% to 85-95%.

## 📊 Current Status

After your test run:
- ✅ Transcript extractor: Working
- ❌ Visual extractor: Not initialized (needs OpenCV)
- ❌ Audio extractor: Not initialized (needs librosa)
- ✅ Gaming classifier: 0.65 confidence (transcript only)
- ❌ Other classifiers: Skipped (need visual/audio features)

---

## 🎯 Improvement Roadmap

### Phase 1: Enable All Extractors (Quick Win)
**Goal:** Get visual and audio extractors working
**Impact:** All classifiers can run, confidence jumps to 75-80%
**Time:** 10-15 minutes

### Phase 2: Expand Keywords (Easy)
**Goal:** Add more keywords to transcript extractor
**Impact:** +5-10% confidence for transcript-only
**Time:** 30 minutes

### Phase 3: Tune Classifier Weights (Medium)
**Goal:** Optimize signal weights in each classifier
**Impact:** +5-10% accuracy
**Time:** 1-2 hours with testing

### Phase 4: Add NLP Enhancement (Advanced)
**Goal:** Enable spaCy, KeyBERT for semantic understanding
**Impact:** +10-15% accuracy, detects synonyms
**Time:** 2-3 hours setup + testing

---

## Phase 1: Enable All Extractors

### Step 1.1: Rebuild Docker Image

The visual and audio libraries are now in `requirements_lambda.txt`:
- `opencv-python-headless` (already there)
- `librosa` (just added)
- `soundfile` (just added)

Rebuild:
```batch
cd C:\Vijay\Work\Clipforge\opus-clip\deployment
.\build-local.bat
```

### Step 1.2: Verify Extractors Load

Run smoke test:
```batch
.\smoke-test-local.bat
```

Look for:
```
✓ Classification system initialized
  Total plugins: 26
  Active plugins: 26  ← Should be 26, not 24!
  Error plugins: 0
```

### Step 1.3: Test with All Features

Run your local test again:
```batch
cd ..
.\run-local-test.bat
```

You should now see:
```
[Orchestrator] Extracted ['transcript', 'visual', 'audio'] using 3 extractors
[Orchestrator] gaming_classifier_v1 classified as 'gaming' with confidence 0.82
                                                                          ↑ Higher!
```

**Expected improvements:**
- Gaming: 0.65 → 0.78-0.85
- Talking Head: Now detects (was skipped)
- Sports: Now detects (was skipped)
- Dance: Now detects (was skipped)

---

## Phase 2: Expand Keywords

### Step 2.1: Add Gaming Keywords

Edit: `classification/plugins/extractors/transcript_extractor.py`

Find the gaming keywords (around line 80):
```python
'gaming': [
    'gg', 'clutch', 'lets go', 'nice', 'op', 'noob'
],
```

Expand to:
```python
'gaming': [
    # Original
    'gg', 'clutch', 'lets go', 'nice', 'op', 'noob',
    # Added
    'epic', 'insane', 'pog', 'poggers', 'cracked',
    'goat', 'lit', 'fire', 'w', 'l', 'ratio',
    'spawn', 'respawn', 'camp', 'camper', 'snipe',
    'headshot', 'killstreak', 'win', 'lose', 'victory',
    'defeat', 'rank', 'ranked', 'competitive', 'casual',
    'tryhard', 'sweaty', 'toxic', 'salty', 'tilted'
],
```

### Step 2.2: Add Other Category Keywords

**Cooking:**
```python
'cooking': [
    # Original
    'add', 'mix', 'cook', 'ingredients', 'recipe',
    # Added
    'stir', 'whisk', 'fold', 'saute', 'simmer',
    'boil', 'bake', 'roast', 'grill', 'fry',
    'chop', 'dice', 'slice', 'mince', 'peel',
    'season', 'taste', 'flavor', 'texture', 'consistency',
    'tablespoon', 'teaspoon', 'cup', 'pinch', 'dash',
    'oven', 'stove', 'pan', 'pot', 'bowl'
],
```

**Fitness:**
```python
'fitness': [
    # Original
    'reps', 'sets', 'exercise', 'workout',
    # Added
    'lift', 'squat', 'deadlift', 'bench press', 'curl',
    'pushup', 'pullup', 'situp', 'plank', 'burpee',
    'cardio', 'hiit', 'sprint', 'jog', 'run',
    'stretch', 'warmup', 'cooldown', 'recovery',
    'muscle', 'gain', 'pump', 'burn', 'shred',
    'protein', 'calories', 'macro', 'bulk', 'cut'
],
```

**Tutorial:**
```python
'tutorial': [
    # Original
    'first', 'next', 'step', 'how to', 'show you',
    # Added
    'follow along', 'tutorial', 'guide', 'walkthrough',
    'demonstrate', 'explain', 'teach', 'learn',
    'easy', 'simple', 'quick', 'beginner', 'advanced',
    'tip', 'trick', 'hack', 'pro tip', 'warning',
    'important', 'remember', 'dont forget', 'make sure'
],
```

### Step 2.3: Test Keyword Changes

After adding keywords, rebuild and test:
```batch
cd deployment
.\build-local.bat
cd ..
.\run-local-test.bat
```

You should see higher confidence:
```
[Test] ✓ Classification Results:
  Category: gaming
  Confidence: 0.78  ← Was 0.65!
```

---

## Phase 3: Tune Classifier Weights

### Step 3.1: Understanding Signal Weights

Each classifier combines multiple signals with weights. Example from gaming_classifier.py:

```python
signals['gaming_keywords'] = keyword_score
weights['gaming_keywords'] = 0.35  # 35% of final score

signals['speech_pattern'] = pattern_score
weights['speech_pattern'] = 0.20  # 20% of final score
```

Final confidence = weighted average of all signals.

### Step 3.2: Adjust Gaming Classifier

Edit: `classification/plugins/classifiers/gaming_classifier.py` (line 90-150)

**Current weights:**
```python
weights = {
    'gaming_keywords': 0.35,    # CRITICAL
    'speech_pattern': 0.20,
    'motion_action': 0.20,
    'audio_intensity': 0.15,
    'composition': 0.10
}
```

**Improve for gaming detection:**
```python
weights = {
    'gaming_keywords': 0.45,    # Increase - keywords are very reliable
    'speech_pattern': 0.25,     # Increase - burst pattern common in gaming
    'motion_action': 0.15,      # Decrease - not always high motion
    'audio_intensity': 0.10,    # Decrease - not always loud
    'composition': 0.05         # Decrease - composition varies
}
```

**Rationale:**
- Gaming keywords are highly specific → increase weight
- Speech pattern (bursts) is very characteristic → increase
- Motion can be low in strategy games → decrease
- Audio can be quiet in stealth games → decrease

### Step 3.3: Tune Other Classifiers

**Talking Head Classifier:** Face detection is critical
```python
weights = {
    'face_presence': 0.50,      # Increase - faces are defining feature
    'face_centered': 0.20,
    'speech_continuous': 0.15,
    'minimal_motion': 0.10,
    'audio_clear': 0.05
}
```

**Cooking Classifier:** Keywords + visual confirmation
```python
weights = {
    'cooking_keywords': 0.40,   # High - specific vocabulary
    'scene_changes': 0.25,      # Moderate - switching between steps
    'hand_movements': 0.20,     # Important - hands preparing food
    'speech_instructional': 0.15
}
```

### Step 3.4: Lower Confidence Threshold

If classifier is too strict, lower min_confidence:

Edit each classifier's `__init__` method:

**Before:**
```python
self._min_confidence = 0.65  # 65% threshold
```

**After:**
```python
self._min_confidence = 0.60  # 60% threshold (more permissive)
```

**⚠️ Warning:** Lower threshold = more classifications, but some false positives.

**Recommended thresholds:**
- Gaming: 0.60 (permissive, gaming is distinct)
- Talking Head: 0.70 (strict, avoid false positives)
- Cooking: 0.65 (moderate)
- Tutorial: 0.60 (permissive, many tutorials)
- Sports: 0.70 (strict, needs visual confirmation)
- Dance: 0.75 (very strict, music + motion required)

---

## Phase 4: Add NLP Enhancement

### Step 4.1: Add NLP Libraries to Docker

Edit: `requirements_lambda.txt`

Add NLP packages:
```txt
# NLP Enhancement (optional - for better accuracy)
spacy==3.7.2
keybert==0.8.4
sentence-transformers==2.2.2
textblob==0.17.1
scikit-learn==1.3.2
```

**Note:** This adds ~200MB to image size.

### Step 4.2: Download spaCy Model in Dockerfile

Edit: `deployment/dockerfiles/Dockerfile.process-clip`

Add after pip install:
```dockerfile
# Download spaCy model for NLP enhancement (optional)
RUN python -m spacy download en_core_web_sm || echo "spaCy model download failed (optional)"
```

### Step 4.3: Rebuild and Test NLP

```batch
cd deployment
.\build-local.bat
```

This will take 10-15 minutes due to larger dependencies.

Test:
```batch
.\smoke-test-local.bat
```

Look for:
```
[NLPTranscript] Loaded spaCy model
[NLPTranscript] Loaded KeyBERT model
[NLPTranscript] Loaded sentence transformer
```

### Step 4.4: NLP Benefits

With NLP enabled:
- Detects synonyms ("awesome" = "epic" = "great")
- Understands context ("sick play" in gaming vs "sick patient" in medical)
- Extracts semantic keywords (not just exact matches)
- Calculates category similarity scores

**Expected improvement:** +10-15% accuracy

**Cost:** Larger image (~400MB vs ~200MB), slower cold start (+2-3 sec)

---

## Testing Your Improvements

### Test Script: Classification Accuracy Test

Create: `test-classification-accuracy.py`

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/var/task')
from classification import get_classification_service

# Test cases with expected categories
test_cases = [
    {
        'text': 'oh my god that clutch play was insane! gg wp',
        'expected': 'gaming',
        'min_confidence': 0.75
    },
    {
        'text': 'first you want to mix the flour and eggs together',
        'expected': 'cooking',
        'min_confidence': 0.70
    },
    {
        'text': 'today im going to show you how to install python',
        'expected': 'tutorial',
        'min_confidence': 0.65
    },
    {
        'text': 'hey guys welcome back to my channel',
        'expected': 'vlog',
        'min_confidence': 0.60
    }
]

# Initialize service
service = get_classification_service()
service.initialize()

# Run tests
correct = 0
total = len(test_cases)

for test in test_cases:
    clip_info = {
        'clip': {
            'text': test['text'],
            'duration': 30.0,
            'segments': []
        }
    }

    classification, _ = service.classify_quick(clip_info)

    if classification:
        category = classification.category
        confidence = classification.confidence

        is_correct = (
            category == test['expected'] and
            confidence >= test['min_confidence']
        )

        status = "✓" if is_correct else "✗"
        if is_correct:
            correct += 1

        print(f"{status} Expected: {test['expected']}, Got: {category} ({confidence:.2f})")
    else:
        print(f"✗ Expected: {test['expected']}, Got: No classification")

accuracy = (correct / total) * 100
print(f"\nAccuracy: {correct}/{total} ({accuracy:.0f}%)")
```

Run:
```batch
docker run --rm opus-process-clip:local-test python test-classification-accuracy.py
```

---

## Monitoring Classification Performance

### Add Detailed Logging

Edit any classifier to add debug logging:

```python
def _calculate_confidence(self, transcript, visual, audio):
    signals = {}
    weights = {}

    # ... calculate signals ...

    # DEBUG: Show signal breakdown
    if os.environ.get('DEBUG_CLASSIFICATION', 'false') == 'true':
        print(f"[DEBUG] {self._metadata.plugin_id} signals:")
        for key, value in signals.items():
            print(f"  {key}: {value:.2f} (weight: {weights[key]:.2f})")
        print(f"  Final confidence: {confidence:.2f}")

    return confidence, reasoning
```

Enable debugging:
```batch
docker run --rm -e DEBUG_CLASSIFICATION=true ...
```

### Track Misclassifications

Keep a log of incorrect classifications:

```json
{
  "text": "...",
  "expected": "gaming",
  "actual": "reaction",
  "confidence": 0.72,
  "reason": "Too many reaction keywords, needs better gaming signal"
}
```

Use this to identify patterns and improve classifiers.

---

## Quick Reference: Improvement Checklist

### ✅ Phase 1 (10-15 min)
- [ ] Add librosa to requirements_lambda.txt
- [ ] Rebuild Docker image
- [ ] Verify all 26 plugins active
- [ ] Test - confidence should increase to 75-80%

### ✅ Phase 2 (30 min)
- [ ] Add 20-30 keywords per category
- [ ] Focus on most-used categories first
- [ ] Test each change
- [ ] Expect +5-10% confidence

### ✅ Phase 3 (1-2 hours)
- [ ] Adjust signal weights in classifiers
- [ ] Lower confidence thresholds if needed
- [ ] Test with variety of clips
- [ ] Expect +5-10% accuracy

### ✅ Phase 4 (2-3 hours)
- [ ] Add spaCy, KeyBERT to requirements
- [ ] Download spaCy model in Dockerfile
- [ ] Rebuild (will be large image)
- [ ] Test NLP extractor
- [ ] Expect +10-15% accuracy

---

## Expected Results

| Phase | Confidence | Active Plugins | Image Size | Build Time |
|-------|-----------|----------------|------------|------------|
| Current | 0.65 | 24/26 | 200MB | 5-10 min |
| Phase 1 | 0.75-0.80 | 26/26 | 250MB | 5-10 min |
| Phase 2 | 0.80-0.85 | 26/26 | 250MB | 5-10 min |
| Phase 3 | 0.85-0.90 | 26/26 | 250MB | 5-10 min |
| Phase 4 | 0.90-0.95 | 26/26 | 400MB | 10-15 min |

**Recommendation:** Start with Phase 1 and 2 for quick wins. Add Phase 3 and 4 only if needed.

---

## Need Help?

Check the logs for clues:
```
[Orchestrator] gaming_classifier_v1 classified as 'gaming' with confidence 0.65
                                                                            ↑
                                                            If too low, check signals
```

Review the reasoning:
```python
print(classification.reasoning)
# Shows which signals contributed most
```

Test individual components:
```python
# Test extractor
features = transcript_extractor.extract(video_path, clip_info)
print(f"Keywords found: {features['keywords']}")

# Test classifier
result = gaming_classifier.classify(features)
print(f"Confidence: {result['confidence']}")
print(f"Reasoning: {result['reasoning']}")
```

Happy improving! 🚀
