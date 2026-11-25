import json
import random
from pathlib import Path
from shuffle_and_gen import shuffle_options

QUIZZES_DIR = Path('quizzes')

def shuffle_all():
    if not QUIZZES_DIR.exists():
        print("Quizzes directory not found!")
        return

    total_files = 0
    total_questions = 0

    for cat_dir in QUIZZES_DIR.iterdir():
        if not cat_dir.is_dir(): continue
        for sub_dir in cat_dir.iterdir():
            if not sub_dir.is_dir(): continue
            for tf in sub_dir.glob('*.json'):
                if tf.name == 'subject_info.json': continue
                try:
                    with open(tf, 'r', encoding='utf-8') as f:
                        tdata = json.load(f)

                    qs = tdata.get('questions', [])
                    if not qs: continue

                    shuffled_qs = []
                    for q in qs:
                        shuffled_qs.append(shuffle_options(q))

                    tdata['questions'] = shuffled_qs

                    with open(tf, 'w', encoding='utf-8') as f:
                        json.dump(tdata, f, ensure_ascii=False, indent=2)

                    total_files += 1
                    total_questions += len(qs)
                except Exception as e:
                    print(f"Error shuffling {tf}: {e}")

    print(f"Successfully shuffled options for {total_questions} questions across {total_files} test files!")

if __name__ == '__main__':
    shuffle_all()
