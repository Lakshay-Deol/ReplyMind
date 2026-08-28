from app.ai.opportunity_detector import detect_opportunities
from app.ai.opportunity_models import OpportunitySignalType
from app.ai.types import CommentCategory, TriageDecision, TriageResult


def make_triage_result(decision=TriageDecision.DRAFT_REPLY, category=CommentCategory.OTHER, spam_score=0.0, relevance_score=0.5):
    return TriageResult(decision=decision, category=category, reasons=[], spam_score=spam_score, relevance_score=relevance_score)

def test_detect_spam():
    res = detect_opportunities("Buy followers at www.spam.com", make_triage_result(TriageDecision.IGNORE))
    assert res.signal_type == OpportunitySignalType.SPAM
    assert "buy followers" in res.explanation.lower() or res.confidence == 0.95

    res2 = detect_opportunities("Hello", make_triage_result(TriageDecision.SPAM, spam_score=0.99))
    assert res2.signal_type == OpportunitySignalType.SPAM
    assert res2.confidence == 0.99

def test_detect_urgent():
    res = detect_opportunities("Help please my account is broken", make_triage_result())
    assert res.signal_type == OpportunitySignalType.URGENT

def test_detect_toxicity():
    res = detect_opportunities("You are an idiot and this is terrible", make_triage_result())
    assert res.signal_type == OpportunitySignalType.TOXICITY

def test_detect_collaboration():
    res = detect_opportunities("We should collaborate on a project", make_triage_result())
    assert res.signal_type == OpportunitySignalType.COLLABORATION

def test_detect_purchase_intent():
    res = detect_opportunities("Where can i buy this tool?", make_triage_result())
    assert res.signal_type == OpportunitySignalType.PURCHASE_INTENT

def test_detect_superfan():
    res = detect_opportunities("This is the third video I've watched from you, huge fan!", make_triage_result())
    assert res.signal_type == OpportunitySignalType.SUPERFAN

def test_detect_content_request():
    res = detect_opportunities("Can you make a video explaining this?", make_triage_result())
    assert res.signal_type == OpportunitySignalType.CONTENT_REQUEST

def test_detect_trend():
    res = detect_opportunities("Everyone is doing this trend right now", make_triage_result())
    assert res.signal_type == OpportunitySignalType.TREND

def test_detect_complaint():
    res = detect_opportunities("This tutorial skipped the most important part", make_triage_result())
    assert res.signal_type == OpportunitySignalType.COMPLAINT

    res2 = detect_opportunities("Not working", make_triage_result(category=CommentCategory.COMPLAINT))
    assert res2.signal_type == OpportunitySignalType.COMPLAINT

def test_detect_faq():
    res = detect_opportunities("What software do you use to edit?", make_triage_result(category=CommentCategory.QUESTION))
    assert res.signal_type == OpportunitySignalType.FAQ

def test_detect_question():
    res = detect_opportunities("How did you build the backend?", make_triage_result(category=CommentCategory.QUESTION))
    assert res.signal_type == OpportunitySignalType.QUESTION

def test_detect_praise():
    res = detect_opportunities("Great job!", make_triage_result(category=CommentCategory.PRAISE))
    assert res.signal_type == OpportunitySignalType.PRAISE

def test_detect_other():
    res = detect_opportunities("Just passing by", make_triage_result(category=CommentCategory.OTHER))
    assert res.signal_type == OpportunitySignalType.OTHER
