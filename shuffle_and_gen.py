"""Utility to shuffle question options and adjust correct option index."""
import random


def shuffle_options(q: dict) -> dict:
    """Shuffle options of a question while updating correct option index."""
    opts = list(q.get("options", []))
    if not opts:
        return dict(q)
    correct_idx = q.get("correct", q.get("answer", 0))
    if not (0 <= correct_idx < len(opts)):
        correct_idx = 0
    correct_val = opts[correct_idx]

    shuffled_opts = list(opts)
    random.shuffle(shuffled_opts)

    new_correct_idx = shuffled_opts.index(correct_val)

    new_q = dict(q)
    new_q["options"] = shuffled_opts
    new_q["correct"] = new_correct_idx
    return new_q
