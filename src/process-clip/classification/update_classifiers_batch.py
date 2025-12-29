"""
Batch Update Script for Adding Object Detection to All Classifiers

This script updates all remaining classifiers to include object detection features.
It follows the same pattern established in gaming_classifier and cooking_classifier.
"""

import re
from pathlib import Path


# Object mappings for each classifier
CLASSIFIER_OBJECTS = {
    'fitness': {
        'objects': ['sports ball', 'bicycle', 'skateboard', 'bench', 'tennis racket'],
        'weight': 0.25,
        'count_threshold': {3: 1.0, 2: 0.9, 1: 0.7},
        'example_text': 'Fitness equipment detected: sports ball, bench'
    },
    'sports': {
        'objects': ['sports ball', 'bicycle', 'skateboard', 'tennis racket', 'baseball bat', 'frisbee'],
        'weight': 0.30,
        'count_threshold': {2: 1.0, 1: 0.8},
        'example_text': 'Sports equipment detected: ball, racket'
    },
    'product_review': {
        'objects': ['cell phone', 'laptop', 'mouse', 'keyboard', 'remote', 'book', 'backpack'],
        'weight': 0.25,
        'count_threshold': {2: 1.0, 1: 0.9},
        'example_text': 'Product detected: cell phone, laptop'
    },
    'dance': {
        'objects': ['person'],
        'weight': 0.15,
        'count_threshold': {1: 0.8},
        'example_text': 'Full body detected in frame'
    },
    'tutorial': {
        'objects': ['book', 'laptop', 'keyboard', 'mouse', 'tv'],
        'weight': 0.20,
        'count_threshold': {2: 0.9, 1: 0.7},
        'example_text': 'Tutorial materials detected: book, laptop'
    },
    'vlog': {
        'objects': ['person', 'car', 'bicycle', 'backpack', 'cell phone'],
        'weight': 0.15,
        'count_threshold': {3: 0.8, 2: 0.7, 1: 0.6},
        'example_text': 'Lifestyle objects detected: car, backpack'
    },
    'talking_head': {
        'objects': ['person', 'chair', 'couch', 'potted plant'],
        'weight': 0.20,
        'count_threshold': {2: 0.9, 1: 0.7},
        'example_text': 'Studio setting detected: chair, couch'
    },
    'news': {
        'objects': ['person', 'tv', 'laptop', 'book', 'chair'],
        'weight': 0.20,
        'count_threshold': {2: 0.9, 1: 0.7},
        'example_text': 'News setting detected: tv, chair'
    },
    'reaction': {
        'objects': ['person', 'chair', 'couch', 'tv'],
        'weight': 0.15,
        'count_threshold': {2: 0.8, 1: 0.6},
        'example_text': 'Reaction setup detected: person, chair'
    }
}


def update_classifier(classifier_path: Path, category: str):
    """
    Update a single classifier file to include object detection

    Args:
        classifier_path: Path to classifier file
        category: Category name (e.g., 'fitness', 'sports')
    """
    print(f"\n[Update] Processing {classifier_path.name}...")

    if category not in CLASSIFIER_OBJECTS:
        print(f"[Update] No object mapping defined for {category}, skipping")
        return

    obj_config = CLASSIFIER_OBJECTS[category]
    objects_list = obj_config['objects']
    weight = obj_config['weight']
    thresholds = obj_config['count_threshold']
    example = obj_config['example_text']

    # Read file
    content = classifier_path.read_text(encoding='utf-8')

    # Check if already updated
    if 'objects: Dict[str, Any]' in content:
        print(f"[Update] {classifier_path.name} already updated, skipping")
        return

    # 1. Update description
    content = re.sub(
        r'(description="[^"]+)',
        r'\1 using NLP + objects',
        content,
        count=1
    )

    # 2. Add "objects" tag
    content = re.sub(
        r'(tags=\[.*?)\]',
        r'\1, "objects"]',
        content,
        count=1
    )

    # 3. Add object_features parameter to classify method
    content = re.sub(
        r'(visual_features = features\.get\(.*?\))\n',
        r'\1\n        object_features = features.get(\'objects\') or {}\n',
        content,
        count=1
    )

    # 4. Update _calculate_confidence call
    content = re.sub(
        r'(confidence, reasoning = self\._calculate_confidence\(\s*transcript_features,\s*visual_features)',
        r'\1,\n            object_features',
        content,
        count=1
    )

    # 5. Update _calculate_confidence signature
    content = re.sub(
        r'(def _calculate_confidence\(\s*self,\s*transcript: Dict\[str, Any\],\s*visual: Dict\[str, Any\])',
        r'\1,\n        objects: Dict[str, Any]',
        content,
        count=1
    )

    # 6. Update docstring
    content = re.sub(
        r'(Args:\s*transcript: Transcript features\s*visual: Visual features)',
        r'\1\n            objects: Object detection features (optional)',
        content,
        count=1
    )

    # 7. Reduce first weight to make room for objects
    # Find first weights assignment and reduce it
    content = re.sub(
        r"(weights\['\w+'\] = )0\.\d+(\s*# .*)?$",
        lambda m: f"{m.group(1)}{float(m.group(0).split('=')[1].split('#')[0].strip()) - 0.05:.2f}{m.group(2) if m.group(2) else '  # Reduced for objects'}",
        content,
        count=1,
        flags=re.MULTILINE
    )

    # 8. Add object detection signal before "Calculate weighted confidence"
    object_signal_code = f'''
        # Signal: Object Detection ({category} objects - STRONG SIGNAL)
        has_{category}_objects = objects.get('has_{category}_objects', False)
        detected_objects = objects.get('detected_objects', {{}})

        object_score = 0.5  # Default

        if has_{category}_objects:
            # Check for specific {category} objects
            {category}_object_count = 0
            {category}_objs_list = []

            for obj in {objects_list}:
                if obj in detected_objects:
                    {category}_object_count += 1
                    {category}_objs_list.append(obj)

            # Strong signal if multiple objects detected
'''

    for count, score in sorted(thresholds.items(), reverse=True):
        if count > 1:
            object_signal_code += f'''            if {category}_object_count >= {count}:
                object_score = {score}
            el'''
        else:
            object_signal_code += f'''            if {category}_object_count == {count}:
                object_score = {score}
            else:
                object_score = 0.6
'''

    object_signal_code += f'''
        # Use object detection category score
        category_scores = objects.get('category_scores', {{}})
        {category}_object_score = category_scores.get('{category}', 0.0)
        if {category}_object_score > 0.3:
            object_score = max(object_score, {category}_object_score)

        signals['{category}_objects'] = object_score
        weights['{category}_objects'] = {weight}

'''

    content = re.sub(
        r'(\s+# Calculate weighted confidence)',
        object_signal_code + r'\1',
        content,
        count=1
    )

    # 9. Update reasoning dict
    content = re.sub(
        r"('key_factors': self\._get_key_factors\(signals, keywords\))",
        r"'key_factors': self._get_key_factors(signals, keywords, objects)",
        content,
        count=1
    )

    # Add object fields to reasoning
    content = re.sub(
        r"(reasoning = \{[^}]+?})",
        lambda m: m.group(0)[:-1] + f",\n            'has_{category}_objects': has_{category}_objects,\n            'detected_objects': list(detected_objects.keys())[:5]\n        }}",
        content,
        count=1,
        flags=re.DOTALL
    )

    # 10. Update _get_key_factors signature
    content = re.sub(
        r'(def _get_key_factors\(self, signals: Dict\[str, float\], keywords: list)\)',
        r'\1, objects: Dict[str, Any])',
        content,
        count=1
    )

    # Update _get_key_factors docstring
    content = re.sub(
        r'(Args:\s*signals: Signal scores dictionary\s*keywords: Detected keywords)',
        r'\1\n            objects: Object detection features',
        content,
        count=1
    )

    # 11. Add object detection check at beginning of _get_key_factors
    obj_check_code = f'''        # Object detection is strongest signal
        if signals.get('{category}_objects', 0) >= 0.8:
            detected = objects.get('detected_objects', {{}})
            {category}_objs = [obj for obj in {objects_list[:3]} if obj in detected]
            if {category}_objs:
                factors.append(f'{example[:-1]}{{", ".join({category}_objs)}}')
            else:
                factors.append('{category.replace("_", " ").title()} objects detected in scene')

'''

    content = re.sub(
        r'(factors = \[\]\n)',
        r'\1\n' + obj_check_code,
        content,
        count=1
    )

    # Write updated content
    classifier_path.write_text(content, encoding='utf-8')
    print(f"[Update] SUCCESS - {classifier_path.name} updated successfully")


def main():
    """Update all classifiers"""
    classifiers_dir = Path(__file__).parent / "plugins" / "classifiers"

    classifiers_to_update = [
        ('fitness_classifier.py', 'fitness'),
        ('sports_classifier.py', 'sports'),
        ('product_review_classifier.py', 'product_review'),
        ('dance_classifier.py', 'dance'),
        ('tutorial_classifier.py', 'tutorial'),
        ('vlog_classifier.py', 'vlog'),
        ('talking_head_classifier.py', 'talking_head'),
        ('news_classifier.py', 'news'),
        ('reaction_classifier.py', 'reaction')
    ]

    print("="*60)
    print("Batch Classifier Update - Adding Object Detection")
    print("="*60)

    for filename, category in classifiers_to_update:
        classifier_path = classifiers_dir / filename
        if classifier_path.exists():
            try:
                update_classifier(classifier_path, category)
            except Exception as e:
                print(f"[ERROR] Failed to update {filename}: {e}")
        else:
            print(f"[SKIP] {filename} not found")

    print("\n" + "="*60)
    print("Update Complete!")
    print("="*60)


if __name__ == "__main__":
    main()
