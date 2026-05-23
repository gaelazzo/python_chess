from datetime import date

from LearningBase import LearningBase, LearnPosition


def make_pos(ok="e2e4"):
    return LearnPosition(
        zobrist=1, fen="x", ok=ok, move=ok, moves="",
        successful=0, ntry=0, white="W", black="B",
    )


def test_correct_move_updates_stats():
    p = make_pos()
    res = LearningBase.updatePositionStats(p, "e2e4", date(2024, 1, 1))
    assert res is True
    assert p.ntry == 1
    assert p.successful == 1
    assert p.serie == 1


def test_marked_learned_after_five_in_a_row():
    p = make_pos()
    for i in range(5):
        LearningBase.updatePositionStats(p, "e2e4", date(2024, 1, 1 + i))
    assert p.successful == 5
    assert p.skip is True


def test_wrong_move_breaks_streak():
    p = make_pos()
    res = LearningBase.updatePositionStats(p, "h2h4", date(2024, 1, 1))
    assert res is False
    assert p.successful == 0
    assert p.serie < 0


def test_max_value_date_returns_later():
    assert LearningBase.maxValueDate(date(2024, 1, 1), date(2024, 6, 1)) == date(2024, 6, 1)
    assert LearningBase.maxValueDate(None, date(2024, 6, 1)) == date(2024, 6, 1)
    assert LearningBase.maxValueDate(date(2024, 6, 1), None) == date(2024, 6, 1)


def test_min_value_date_returns_earlier():
    assert LearningBase.minValueDate(date(2024, 6, 1), date(2024, 1, 1)) == date(2024, 1, 1)
    assert LearningBase.minValueDate(date(2024, 1, 1), date(2024, 6, 1)) == date(2024, 1, 1)
    assert LearningBase.minValueDate(None, date(2024, 6, 1)) == date(2024, 6, 1)
    assert LearningBase.minValueDate(date(2024, 6, 1), None) == date(2024, 6, 1)
