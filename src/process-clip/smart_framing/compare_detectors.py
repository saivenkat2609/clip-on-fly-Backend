"""
Face Detector Comparison Script

Compare different face detection models side-by-side on the same video.
Generates statistics, visualizations, and performance metrics to help
choose the best detector for your use case.

Usage:
    python compare_detectors.py --video path/to/video.mp4 --output comparison/
"""

import argparse
import time
import os
from typing import List, Dict
from face_detector_factory import FaceDetectorFactory


def compare_detectors(
    video_path: str,
    output_dir: str,
    start_sec: float = 0,
    duration: float = 10,
    sample_rate: int = 2
):
    """
    Compare multiple face detection models on the same video.

    Args:
        video_path: Path to test video
        output_dir: Directory to save comparison results
        start_sec: Start time in seconds
        duration: Duration to process in seconds
        sample_rate: Frame sampling rate

    Returns:
        Dictionary with comparison results
    """
    print("=" * 80)
    print("FACE DETECTOR COMPARISON")
    print("=" * 80)
    print(f"Video: {video_path}")
    print(f"Time range: {start_sec:.2f}s to {start_sec + duration:.2f}s")
    print(f"Sample rate: every {sample_rate} frame(s)")
    print()

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Models to compare
    models = [
        {
            'name': 'MediaPipe Original',
            'backend': 'mediapipe',
            'params': {'confidence_threshold': 0.6}
        },
        {
            'name': 'MediaPipe Improved',
            'backend': 'mediapipe_improved',
            'params': {'confidence_threshold': 0.7, 'min_face_size': 30}
        },
        {
            'name': 'RetinaFace',
            'backend': 'retinaface',
            'params': {'confidence_threshold': 0.75, 'min_face_size': 30}
        }
    ]

    results = {}
    end_sec = start_sec + duration

    for model_config in models:
        model_name = model_config['name']
        backend = model_config['backend']
        params = model_config['params']

        print(f"\n{'=' * 80}")
        print(f"Testing: {model_name}")
        print(f"{'=' * 80}")

        try:
            # Create detector
            detector = FaceDetectorFactory.create(
                backend=backend,
                **params
            )

            # Time the detection
            start_time = time.time()

            detections = detector.detect_faces_in_video(
                video_path,
                start_sec=start_sec,
                end_sec=end_sec,
                sample_rate=sample_rate
            )

            processing_time = time.time() - start_time

            # Get statistics
            stats = detector.get_face_statistics(detections)
            stats['processing_time_sec'] = processing_time
            stats['fps'] = len(detections) / processing_time if processing_time > 0 else 0

            # Create visualization
            output_path = os.path.join(
                output_dir,
                f"{backend}_annotated.mp4"
            )

            print(f"\n[Comparison] Creating visualization: {output_path}")
            if hasattr(detector, 'visualize_detections'):
                try:
                    detector.visualize_detections(
                        video_path,
                        detections,
                        output_path,
                        start_sec,
                        end_sec
                    )
                except Exception as e:
                    print(f"[Comparison] Warning: Visualization failed: {e}")

            # Store results
            results[model_name] = {
                'backend': backend,
                'params': params,
                'stats': stats,
                'detections': detections
            }

            # Print summary
            print(f"\n{'─' * 80}")
            print(f"SUMMARY - {model_name}")
            print(f"{'─' * 80}")
            print(f"Processing time: {processing_time:.2f}s ({stats['fps']:.1f} fps)")
            print(f"Total faces detected: {stats['total_faces']}")
            print(f"Frames with faces: {stats['frames_with_faces']}/{stats['total_frames']}")
            print(f"Coverage: {stats['coverage_percent']:.1f}%")
            print(f"Avg confidence: {stats['avg_confidence']:.3f}")
            print(f"Avg face size: {stats['avg_face_size_px']:.0f}px²")

        except Exception as e:
            print(f"\n[ERROR] Failed to test {model_name}: {e}")
            import traceback
            traceback.print_exc()
            results[model_name] = {'error': str(e)}

    # Generate comparison report
    print(f"\n\n{'=' * 80}")
    print("COMPARISON REPORT")
    print(f"{'=' * 80}\n")

    # Create comparison table
    print(f"{'Model':<25} {'Faces':<10} {'Coverage':<12} {'Conf':<10} {'Time':<10} {'FPS':<10}")
    print("─" * 85)

    for model_name, result in results.items():
        if 'error' in result:
            print(f"{model_name:<25} ERROR: {result['error']}")
            continue

        stats = result['stats']
        print(
            f"{model_name:<25} "
            f"{stats['total_faces']:<10} "
            f"{stats['coverage_percent']:>6.1f}%     "
            f"{stats['avg_confidence']:<10.3f} "
            f"{stats['processing_time_sec']:>6.2f}s   "
            f"{stats['fps']:>6.1f}"
        )

    # Recommendations
    print(f"\n{'=' * 80}")
    print("RECOMMENDATIONS")
    print(f"{'=' * 80}\n")

    # Find best by different criteria
    valid_results = {k: v for k, v in results.items() if 'error' not in v}

    if valid_results:
        # Most faces detected
        most_faces = max(valid_results.items(), key=lambda x: x[1]['stats']['total_faces'])
        print(f"✓ Most faces detected: {most_faces[0]} ({most_faces[1]['stats']['total_faces']} faces)")

        # Best coverage
        best_coverage = max(valid_results.items(), key=lambda x: x[1]['stats']['coverage_percent'])
        print(f"✓ Best coverage: {best_coverage[0]} ({best_coverage[1]['stats']['coverage_percent']:.1f}%)")

        # Highest confidence
        highest_conf = max(valid_results.items(), key=lambda x: x[1]['stats']['avg_confidence'])
        print(f"✓ Highest avg confidence: {highest_conf[0]} ({highest_conf[1]['stats']['avg_confidence']:.3f})")

        # Fastest processing
        fastest = min(valid_results.items(), key=lambda x: x[1]['stats']['processing_time_sec'])
        print(f"✓ Fastest processing: {fastest[0]} ({fastest[1]['stats']['processing_time_sec']:.2f}s)")

        # Overall recommendation
        print("\n" + "─" * 80)
        print("OVERALL RECOMMENDATION:")
        print("─" * 80)
        print("""
For your use case (small faces missed + false positives):
1. Try RetinaFace first - Best accuracy, fewer false positives
2. If too slow, use MediaPipe Improved - Good balance
3. Avoid original MediaPipe - Known false positive issues

Key settings to tune:
- confidence_threshold: 0.7-0.8 (higher = fewer false positives)
- min_face_size: 25-40px (lower = detect smaller faces)
- sample_rate: 2-5 (lower = more accurate, slower)
""")

    # Save results to file
    report_path = os.path.join(output_dir, 'comparison_report.txt')
    with open(report_path, 'w') as f:
        f.write("FACE DETECTOR COMPARISON REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Video: {video_path}\n")
        f.write(f"Time range: {start_sec:.2f}s to {end_sec:.2f}s\n")
        f.write(f"Sample rate: every {sample_rate} frame(s)\n\n")

        for model_name, result in results.items():
            f.write(f"\n{model_name}\n")
            f.write("-" * 80 + "\n")
            if 'error' in result:
                f.write(f"ERROR: {result['error']}\n")
            else:
                stats = result['stats']
                f.write(f"Total faces: {stats['total_faces']}\n")
                f.write(f"Coverage: {stats['coverage_percent']:.1f}%\n")
                f.write(f"Avg confidence: {stats['avg_confidence']:.3f}\n")
                f.write(f"Processing time: {stats['processing_time_sec']:.2f}s\n")
                f.write(f"FPS: {stats['fps']:.1f}\n")

    print(f"\n✓ Report saved to: {report_path}")
    print(f"✓ Annotated videos saved to: {output_dir}")

    return results


def main():
    """Command-line interface for detector comparison."""
    parser = argparse.ArgumentParser(
        description='Compare face detection models',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--video',
        required=True,
        help='Path to video file'
    )

    parser.add_argument(
        '--output',
        default='./comparison_output',
        help='Output directory for results (default: ./comparison_output)'
    )

    parser.add_argument(
        '--start',
        type=float,
        default=0,
        help='Start time in seconds (default: 0)'
    )

    parser.add_argument(
        '--duration',
        type=float,
        default=10,
        help='Duration to process in seconds (default: 10)'
    )

    parser.add_argument(
        '--sample-rate',
        type=int,
        default=2,
        help='Frame sampling rate (default: 2 = every other frame)'
    )

    args = parser.parse_args()

    # Run comparison
    results = compare_detectors(
        video_path=args.video,
        output_dir=args.output,
        start_sec=args.start,
        duration=args.duration,
        sample_rate=args.sample_rate
    )

    print("\n" + "=" * 80)
    print("Comparison complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()
