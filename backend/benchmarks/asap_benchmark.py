import pandas as pd
import sys
import os
import json
from pathlib import Path

# Enforce UTF-8 encoding for stdout to handle unicode characters on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.scoring_service import score_answer

def run_benchmark(csv_path: str, sample_size: int = 100):
    """
    Run ScorePilot scoring against ASAP 2.0 dataset.
    
    Args:
        csv_path: Path to the ASAP2_train_sourcetexts.csv file
        sample_size: Number of essays to test (default 100)
    """
    
    print(f"\n{'='*60}")
    print("ScorePilot AI — ASAP Benchmark")
    print(f"{'='*60}\n")
    
    # Load dataset
    print(f"Loading dataset from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"Total essays in dataset: {len(df)}")
    
    # Use only columns we need
    df = df[['full_text', 'score']].dropna()
    df = df.head(sample_size)
    print(f"Testing on {len(df)} essays\n")
    
    # Model answer for ASAP 2.0 prompt (about space exploration)
    MODEL_ANSWER = """
    The chapter explores themes of space exploration, scientific
    discovery, and human curiosity. It discusses Venus and other
    planets, the challenges of space travel, and the importance
    of scientific research. Key concepts include planetary science,
    astronomy, and the value of exploring the unknown for human
    knowledge and progress.
    """
    
    # Score range in ASAP 2.0 is 0-4, normalize to match
    MAX_MARKS = 4.0
    
    results = []
    errors = 0
    
    print("Running AI scoring...")
    print("-" * 40)
    
    for idx, row in df.iterrows():
        try:
            # Run ScorePilot scoring
            result = score_answer(
                student_answer=str(row['full_text']),
                model_answer=MODEL_ANSWER,
                question_type='long',
                max_marks=MAX_MARKS
            )
            
            human_score = float(row['score'])
            ai_score = round(float(result['score']), 2)
            confidence = round(float(result.get('confidence', 0)), 2)
            diff = abs(human_score - ai_score)
            
            results.append({
                'human_score': human_score,
                'ai_score': ai_score,
                'confidence': confidence,
                'difference': round(diff, 2),
                'within_0_5': diff <= 0.5,
                'within_1_0': diff <= 1.0,
                'flagged': result.get('flagged_for_review', False)
            })
            
            # Show progress every 10 essays
            if (len(results)) % 10 == 0:
                print(f"  Processed {len(results)}/{sample_size} essays...")
                
        except Exception as e:
            errors += 1
            print(f"  Error on essay {idx}: {e}")
    
    print(f"\nCompleted. {errors} errors skipped.\n")
    
    # Calculate metrics
    total = len(results)
    if total == 0:
        print("No results to analyze.")
        return
    
    mae = sum(r['difference'] for r in results) / total
    within_half = sum(1 for r in results if r['within_0_5']) / total * 100
    within_one = sum(1 for r in results if r['within_1_0']) / total * 100
    flagged_count = sum(1 for r in results if r['flagged'])
    avg_confidence = sum(r['confidence'] for r in results) / total
    
    # Score distribution comparison
    human_avg = sum(r['human_score'] for r in results) / total
    ai_avg = sum(r['ai_score'] for r in results) / total
    
    # Print report
    print(f"{'='*60}")
    print("BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(f"  Total essays tested:        {total}")
    print(f"  Errors/skipped:             {errors}")
    print(f"")
    print(f"ACCURACY METRICS:")
    print(f"  Mean Absolute Error (MAE):  {mae:.3f}")
    print(f"  Within 0.5 marks:           {within_half:.1f}%")
    print(f"  Within 1.0 mark:            {within_one:.1f}%")
    print(f"")
    print(f"SCORE DISTRIBUTION:")
    print(f"  Human avg score:            {human_avg:.2f} / {MAX_MARKS}")
    print(f"  AI avg score:               {ai_avg:.2f} / {MAX_MARKS}")
    print(f"  Score difference (bias):    {abs(human_avg - ai_avg):.3f}")
    print(f"")
    print(f"CONFIDENCE:")
    print(f"  Average AI confidence:      {avg_confidence:.1%}")
    print(f"  Flagged for review:         {flagged_count} ({flagged_count/total*100:.1f}%)")
    print(f"{'='*60}")
    
    # Interpretation
    print("\nINTERPRETATION:")
    if mae < 0.5:
        print("  ✅ EXCELLENT — MAE < 0.5, production-ready accuracy")
    elif mae < 1.0:
        print("  ✅ GOOD — MAE < 1.0, suitable for assisted grading")
    elif mae < 1.5:
        print("  ⚠️  MODERATE — MAE < 1.5, needs human review for most")
    else:
        print("  ❌ POOR — MAE > 1.5, AI scoring needs improvement")
    
    if within_one >= 80:
        print(f"  ✅ {within_one:.0f}% of scores within 1 mark — reliable")
    else:
        print(f"  ⚠️  Only {within_one:.0f}% within 1 mark — needs tuning")
    
    # Save detailed results to JSON
    output_path = Path(__file__).parent / 'benchmark_results.json'
    with open(output_path, 'w') as f:
        json.dump({
            'summary': {
                'total_tested': total,
                'mae': round(mae, 3),
                'within_0_5_percent': round(within_half, 1),
                'within_1_0_percent': round(within_one, 1),
                'avg_confidence': round(avg_confidence, 3),
                'flagged_percent': round(flagged_count/total*100, 1),
                'human_avg': round(human_avg, 2),
                'ai_avg': round(ai_avg, 2),
            },
            'per_essay': results[:20]  # save first 20 for inspection
        }, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_path}")
    print(f"{'='*60}\n")
    
    return {
        'mae': mae,
        'within_1_0_percent': within_one,
        'avg_confidence': avg_confidence
    }


if __name__ == "__main__":
    # Default path — change this to where you saved the CSV
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "ASAP2_train_sourcetexts.csv"
    
    if not os.path.exists(csv_path):
        print(f"Error: File not found: {csv_path}")
        print("Usage: python benchmarks/asap_benchmark.py path/to/ASAP2_train_sourcetexts.csv")
        sys.exit(1)
    
    run_benchmark(csv_path, sample_size=100)
