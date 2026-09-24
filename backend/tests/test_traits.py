from app.persona.models import Trait
from app.persona.traits import extract_traits, usable_by_clone
from tests.fakes import FakeLLM


def test_extract_traits_parses_clean_json_array():
    llm = FakeLLM(reply='[{"text": "favourite food is biryani"}]')
    traits = extract_traits("What's your favourite food?", "Biryani, hands down.", llm)
    assert len(traits) == 1
    assert traits[0].text == "favourite food is biryani"
    assert traits[0].about_person_id is None
    assert traits[0].said_to_their_face is False


def test_extract_traits_parses_json_wrapped_in_markdown_fence():
    llm = FakeLLM(reply='```json\n[{"text": "loves rainy days"}]\n```')
    traits = extract_traits("What's your favourite weather?", "I love rain.", llm)
    assert [t.text for t in traits] == ["loves rainy days"]


def test_extract_traits_handles_extra_prose_around_json():
    llm = FakeLLM(reply='Sure, here you go:\n[{"text": "hates mornings"}]\nHope that helps!')
    traits = extract_traits("Are you a morning person?", "God, no.", llm)
    assert [t.text for t in traits] == ["hates mornings"]


def test_extract_traits_with_person_and_said_to_face_fields():
    llm = FakeLLM(reply='[{"text": "thinks Riya is the funniest person they know", '
                  '"about_person_id": 3, "said_to_their_face": true}]')
    traits = extract_traits("What do you love about Riya?", "She's hilarious, I tell her all the time.", llm)
    assert traits[0].about_person_id == 3
    assert traits[0].said_to_their_face is True


def test_extract_traits_returns_empty_list_for_empty_answer():
    llm = FakeLLM(reply='[{"text": "should never be reached"}]')
    assert extract_traits("Anything else?", "   ", llm) == []


def test_extract_traits_returns_empty_list_on_garbage_output():
    llm = FakeLLM(reply="not json at all")
    assert extract_traits("q", "a", llm) == []


def test_extract_traits_skips_malformed_items_but_keeps_valid_ones():
    llm = FakeLLM(reply='[{"not_text": "oops"}, {"text": "keeps journals"}]')
    traits = extract_traits("q", "a", llm)
    assert [t.text for t in traits] == ["keeps journals"]


def _trait(**kwargs) -> Trait:
    defaults = dict(text="x", source="stated", confirmed=False, about_person_id=None, said_to_their_face=False)
    defaults.update(kwargs)
    return Trait(**defaults)


def test_stated_trait_is_usable_by_clone_even_if_unconfirmed():
    traits = [_trait(source="stated", confirmed=False)]
    assert usable_by_clone(traits, visitor_id=None) == traits


def test_inferred_unconfirmed_trait_is_never_usable_by_clone():
    traits = [_trait(source="inferred", confirmed=False)]
    assert usable_by_clone(traits, visitor_id=None) == []


def test_inferred_confirmed_trait_is_usable_by_clone():
    traits = [_trait(source="inferred", confirmed=True)]
    assert usable_by_clone(traits, visitor_id=None) == traits


def test_trait_about_visitor_hidden_unless_said_to_their_face():
    hidden = _trait(source="stated", about_person_id=7, said_to_their_face=False)
    shown = _trait(source="stated", about_person_id=7, said_to_their_face=True)
    result = usable_by_clone([hidden, shown], visitor_id=7)
    assert result == [shown]


def test_trait_about_someone_else_is_unaffected_by_face_rule():
    trait = _trait(source="stated", about_person_id=7, said_to_their_face=False)
    assert usable_by_clone([trait], visitor_id=99) == [trait]
    assert usable_by_clone([trait], visitor_id=None) == [trait]
