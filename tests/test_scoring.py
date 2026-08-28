from app.ai.scoring import HIGH_PRIORITY_THRESHOLD, calculate_priority


def test_unsupplied_dimensions_do_not_penalise():
    """Only measured dimensions are scored.

    Regression: every unsupplied factor used to count as 0.0 against the full
    100-point scale, so nothing the detector produced could reach the
    high-priority band.
    """
    partial = calculate_priority(sentiment_risk=1.0, relevance=1.0)
    assert partial == 100


def test_high_priority_band_is_reachable_from_detector_inputs():
    # The exact call the URGENT branch of the detector makes.
    score = calculate_priority(engagement=0.5, relevance=0.65, sentiment_risk=1.0)
    assert score >= HIGH_PRIORITY_THRESHOLD


def test_all_zero_is_zero_and_all_one_is_one_hundred():
    assert calculate_priority(engagement=0.0, relevance=0.0) == 0
    assert (
        calculate_priority(
            engagement=1.0,
            relevance=1.0,
            recurrence=1.0,
            sentiment_risk=1.0,
            creator_goals_alignment=1.0,
        )
        == 100
    )


def test_no_dimensions_supplied_scores_zero():
    assert calculate_priority() == 0


def test_inputs_are_clamped():
    assert calculate_priority(relevance=5.0) == 100
    assert calculate_priority(relevance=-3.0) == 0


def test_weighting_favours_sentiment_over_engagement():
    risky = calculate_priority(sentiment_risk=1.0, engagement=0.0)
    chatty = calculate_priority(sentiment_risk=0.0, engagement=1.0)
    assert risky > chatty
