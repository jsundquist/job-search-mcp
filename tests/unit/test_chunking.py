from job_search_mcp.chunking import chunk_resume_text


def test_splits_on_short_section_headers():
    text = "Summary\nSome intro text about the candidate.\nSkills\nPython, Go, AWS"

    chunks = chunk_resume_text(text)

    assert chunks == [
        "Summary\nSome intro text about the candidate.",
        "Skills\nPython, Go, AWS",
    ]


def test_bullets_stay_with_preceding_role_until_next_role_header():
    lines = [
        "Experience",
        "Senior Engineer | Acme Corp   2019 - 2022",
        "* Built the payments platform.",
        "* Led a team of 4 engineers.",
        "Staff Engineer | Beta Inc   2022 - 2024",
        "* Migrated infra to Kubernetes.",
    ]
    text = "\n".join(lines)

    chunks = chunk_resume_text(text)

    expected_first_chunk = "\n".join(lines[:4])
    expected_second_chunk = "\n".join(lines[4:])
    assert chunks == [expected_first_chunk, expected_second_chunk]


def test_role_header_only_splits_after_bulleted_content():
    # No bullets yet, so consecutive header-ish lines accumulate together.
    lines = [
        "Experience",
        "Senior Engineer | Acme Corp   2019 - 2022",
        "Still no bullet points appear in this line.",
    ]
    text = "\n".join(lines)

    chunks = chunk_resume_text(text)

    assert chunks == [text]


def test_blank_lines_are_ignored():
    text = "Summary\n\n\nSome longer intro text about the candidate profile.\n\nSkills\nPython, Go"

    chunks = chunk_resume_text(text)

    assert chunks == [
        "Summary\nSome longer intro text about the candidate profile.",
        "Skills\nPython, Go",
    ]


def test_empty_text_returns_no_chunks():
    assert chunk_resume_text("") == []
