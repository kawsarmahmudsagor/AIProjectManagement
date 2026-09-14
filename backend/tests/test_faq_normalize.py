"""normalize_faq() must be total: every case below is a malformed/adversarial or
generic-filler provider response, and every assertion checks that nothing raises and the
repaired result matches the "repair, don't reject" contract described in
services/faq_service.py's docstring — including that fewer than MAX_FAQ_ITEMS (even zero)
is a valid outcome, not a failure.
"""

from app.services.faq_service import MAX_FAQ_ITEMS, normalize_faq


def _questions(result):
    return [item.question for item in result.items]


def test_not_a_dict_or_missing_items_yields_empty_result():
    assert normalize_faq({}).items == []
    assert normalize_faq({"items": "not-a-list"}).items == []
    assert normalize_faq("garbage").items == []


def test_drops_items_with_empty_question_or_answer():
    raw = {
        "items": [
            {"question": "", "answer": "An answer with no question."},
            {"question": "A question with no answer.", "answer": ""},
            {"question": "Why did the retry queue need custom backoff?", "answer": "Because vendor limits varied."},
        ]
    }
    result = normalize_faq(raw)
    assert len(result.items) == 1
    assert result.items[0].question == "Why did the retry queue need custom backoff?"


def test_drops_non_dict_entries():
    raw = {"items": ["not-a-dict", 42, None, {"question": "Q?", "answer": "A."}]}
    result = normalize_faq(raw)
    assert len(result.items) == 1


def test_drops_generic_questions():
    raw = {
        "items": [
            {"question": "What technologies were used in this project?", "answer": "Python and React."},
            {"question": "What was your role on this project?", "answer": "Backend engineer."},
            {"question": "How long did the project take?", "answer": "Six months."},
            {"question": "What was this project about?", "answer": "A tool for X."},
            {
                "question": "Why was a custom caching layer needed instead of an off-the-shelf CDN?",
                "answer": "Because responses depended on per-user permissions that a CDN could not evaluate.",
            },
        ]
    }
    result = normalize_faq(raw)
    assert _questions(result) == [
        "Why was a custom caching layer needed instead of an off-the-shelf CDN?"
    ]


def test_dedupes_case_insensitively_identical_questions():
    raw = {
        "items": [
            {"question": "Why was X chosen over Y?", "answer": "Because of Z."},
            {"question": "why was x chosen over y?", "answer": "A slightly different phrasing of the same answer."},
        ]
    }
    result = normalize_faq(raw)
    assert len(result.items) == 1


def test_caps_at_max_faq_items():
    raw = {"items": [{"question": f"Distinct question {i}?", "answer": f"Answer {i}."} for i in range(20)]}
    result = normalize_faq(raw)
    assert len(result.items) == MAX_FAQ_ITEMS


def test_truncates_overlong_question_and_answer_at_word_boundary():
    long_question = "Why " + ("word " * 100) + "?"
    long_answer = "Because " + ("reason " * 200)
    raw = {"items": [{"question": long_question, "answer": long_answer}]}
    result = normalize_faq(raw)
    item = result.items[0]
    assert len(item.question) <= 203  # _MAX_QUESTION_LEN + len("...")
    assert len(item.answer) <= 603  # _MAX_ANSWER_LEN + len("...")
    assert item.question.endswith("...")
    assert item.answer.endswith("...")


def test_zero_items_is_a_valid_result_not_an_error():
    raw = {"items": [{"question": "What technologies were used?", "answer": "Python."}]}
    result = normalize_faq(raw)
    assert result.items == []
