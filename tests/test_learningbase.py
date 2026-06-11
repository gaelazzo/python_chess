from datetime import date

from config import config
from LearningBase import LearningBase, LearnPosition


def make_pos(ok="e2e4"):
    return LearnPosition(
        zobrist=1, fen="x", ok=ok, move=ok, moves="",
        successful=0, ntry=0, white="W", black="B",
    )


def _learn_threshold():
    return config.correctsToLearn or 5


def test_correct_move_updates_stats():
    p = make_pos()
    res = LearningBase.updatePositionStats(p, "e2e4", date(2024, 1, 1))
    assert res is True
    assert p.ntry == 1
    assert p.successful == 1
    assert p.serie == 1


def test_marked_learned_after_threshold_in_a_row():
    n = _learn_threshold()
    p = make_pos()
    # one short of the threshold: not learned yet
    for i in range(n - 1):
        LearningBase.updatePositionStats(p, "e2e4", date(2024, 1, 1 + i))
    assert p.skip is False
    # the threshold-th consecutive correct flips it to learned
    LearningBase.updatePositionStats(p, "e2e4", date(2024, 1, 1 + n))
    assert p.successful == n
    assert p.skip is True


def test_wrong_move_breaks_streak():
    p = make_pos()
    res = LearningBase.updatePositionStats(p, "h2h4", date(2024, 1, 1))
    assert res is False
    assert p.successful == 0
    assert p.serie < 0


def test_wrong_revives_learned_position():
    """A wrong answer on a skip=True position brings it back (local revive),
    and `serie` is left negative so the learn streak must restart from scratch."""
    n = _learn_threshold()
    p = make_pos()
    for i in range(n):
        LearningBase.updatePositionStats(p, "e2e4", date(2024, 1, 1 + i))
    assert p.skip is True
    res = LearningBase.updatePositionStats(p, "h2h4", date(2024, 2, 1))   # wrong
    assert res is False
    assert p.skip is False        # revived
    assert p.serie < 0            # streak reset, won't re-skip on the next single correct


def test_revive_learned_clears_only_learned(monkeypatch):
    lb = LearningBase(movesToAnalyze=1, blunderValue=1, ponderTime=0.1, useBook=False)
    learned = make_pos("e2e4")
    learned.zobrist, learned.skip, learned.serie = 1, True, 7
    learned.successful, learned.ntry = 9, 12
    fresh = make_pos("d2d4")
    fresh.zobrist, fresh.skip, fresh.serie = 2, False, 2
    lb.positions = {1: learned, 2: fresh}
    monkeypatch.setattr(lb, "save", lambda *a, **k: None)   # don't touch data/

    n = lb.reviveLearned()
    assert n == 1                                   # only the learned one counted
    assert learned.skip is False and learned.serie == 0
    assert learned.successful == 9 and learned.ntry == 12   # history preserved
    assert fresh.skip is False and fresh.serie == 2          # untouched


def test_max_value_date_returns_later():
    assert LearningBase.maxValueDate(date(2024, 1, 1), date(2024, 6, 1)) == date(2024, 6, 1)
    assert LearningBase.maxValueDate(None, date(2024, 6, 1)) == date(2024, 6, 1)
    assert LearningBase.maxValueDate(date(2024, 6, 1), None) == date(2024, 6, 1)


def test_min_value_date_returns_earlier():
    assert LearningBase.minValueDate(date(2024, 6, 1), date(2024, 1, 1)) == date(2024, 1, 1)
    assert LearningBase.minValueDate(date(2024, 1, 1), date(2024, 6, 1)) == date(2024, 1, 1)
    assert LearningBase.minValueDate(None, date(2024, 6, 1)) == date(2024, 6, 1)
    assert LearningBase.minValueDate(date(2024, 6, 1), None) == date(2024, 6, 1)
