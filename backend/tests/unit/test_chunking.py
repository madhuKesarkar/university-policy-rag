import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ingestion.chunk import CHUNK_SIZE, chunk_elements
from ingestion.extract import Element

pytestmark = pytest.mark.unit


def el(text, heading="1. Intro", page=1, is_heading=False):
    return Element(text=text, page_number=page, heading=heading, is_heading=is_heading)


# --- example-based tests: one scenario each ---------------------------------

def test_empty_input_gives_no_chunks():
    assert chunk_elements([]) == []


def test_heading_elements_are_not_chunked():
    chunks = chunk_elements([el("1. Intro", is_heading=True), el("Body text.")])
    assert [c.content for c in chunks] == ["Body text."]


def test_short_section_stays_one_chunk_with_metadata():
    chunks = chunk_elements([el("Para one.", page=3), el("Para two.", page=3)])
    assert len(chunks) == 1
    assert chunks[0].content == "Para one.\n\nPara two."
    assert chunks[0].section_heading == "1. Intro"
    assert chunks[0].page_number == 3


def test_chunk_never_spans_two_sections():
    chunks = chunk_elements([el("Alpha.", heading="1. A"), el("Beta.", heading="2. B")])
    assert [(c.section_heading, c.content) for c in chunks] == [("1. A", "Alpha."), ("2. B", "Beta.")]


def test_long_section_is_split_and_overlaps():
    sentence = "Students must submit the override form before week two. "
    chunks = chunk_elements([el(sentence * 40)])
    assert len(chunks) > 1
    # overlap: the end of chunk 1 shows up again at the start of chunk 2
    assert chunks[0].content[-30:].split()[-1] in chunks[1].content[:150]


# --- property-based tests: Hypothesis generates hundreds of inputs ----------

words = st.text(alphabet=st.characters(whitelist_categories=("L", "N")), min_size=1, max_size=15)
paragraph = st.lists(words, min_size=1, max_size=300).map(" ".join)
headings = st.sampled_from(["1. Intro", "2. Rules", "3. Appeals", None])
elements = st.lists(
    st.builds(el, text=paragraph, heading=headings, page=st.integers(1, 20)),
    min_size=1,
    max_size=8,
)


@settings(max_examples=200)
@given(elements)
def test_no_chunk_exceeds_max_size(els):
    for chunk in chunk_elements(els):
        assert len(chunk.content) <= CHUNK_SIZE


@settings(max_examples=200)
@given(elements)
def test_no_empty_chunks(els):
    for chunk in chunk_elements(els):
        assert chunk.content.strip() != ""


@settings(max_examples=200)
@given(elements)
def test_every_chunk_comes_from_its_own_section(els):
    for chunk in chunk_elements(els):
        section_text = " ".join(e.text for e in els if e.heading == chunk.section_heading)
        for word in chunk.content.split():
            assert word in section_text


@settings(max_examples=200)
@given(elements)
def test_no_words_are_lost(els):
    all_chunk_text = " ".join(c.content for c in chunk_elements(els))
    for e in els:
        for word in e.text.split():
            assert word in all_chunk_text