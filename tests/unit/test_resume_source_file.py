from pathlib import Path

import pytest

from job_search_mcp.resume_source.file_source import FileResumeSource

FIXTURES = Path(__file__).parent.parent / "fixtures" / "resumes"


@pytest.mark.parametrize(
    "filename",
    ["sample_resume.txt", "sample_resume.md", "sample_resume.pdf", "sample_resume.docx"],
)
def test_get_content_extracts_expected_text(filename):
    content = FileResumeSource(FIXTURES / filename).get_content()

    assert "Jane Example" in content
    assert "Python" in content


def test_unsupported_extension_raises():
    with pytest.raises(ValueError, match="Unsupported resume file type"):
        FileResumeSource(FIXTURES / "not_a_resume.xyz").get_content()
