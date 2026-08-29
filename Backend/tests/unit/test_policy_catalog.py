"""The policy catalogue is the single source of truth for policy metadata."""

from app.domain.policy_catalog import POLICY_CATALOG, english_documents, title_for


def test_the_catalogue_holds_every_document_in_both_languages():
    assert len(POLICY_CATALOG) == 14
    assert len(english_documents()) == 9


def test_expense_policy_has_one_agreed_title():
    """
    This title was spelled two different ways across five files. The copy that wrote
    titles into the search index disagreed with the other four, so the title a reader saw
    on a citation depended on which code path produced it.
    """
    assert title_for("HC-PC-005") == "Expense Claims & Reimbursement Policy"


def test_every_document_can_build_its_own_download_link():
    for document in POLICY_CATALOG.values():
        assert document.pdf_url.startswith("/api/v1/hcs01/policies/pdf/")
        assert document.pdf_url.endswith(".pdf")


def test_every_document_is_backed_by_a_markdown_source():
    """
    Content comes from Markdown, which is the policy. Documents used to carry a
    hand-typed paragraph describing a flowchart image as well, and those paragraphs were
    a third statement of the same rules that agreed with neither the Markdown nor the
    PDF. The processes they described are written into the policies now.
    """
    for document in POLICY_CATALOG.values():
        assert document.markdown_filename, f"{document.code} has no source document"


def test_arabic_documents_are_titled_in_arabic():
    arabic_document = POLICY_CATALOG["HC-PC-001-AR"]

    assert arabic_document.language == "ar"
    assert any("؀" <= character <= "ۿ" for character in arabic_document.title)


def test_the_arabic_editions_track_the_english_section_numbering():
    """A citation has to mean the same clause in either language."""
    for code, document in POLICY_CATALOG.items():
        if document.language != "ar":
            continue
        english = POLICY_CATALOG[code.removesuffix("-AR")]
        assert document.markdown_filename == english.markdown_filename


def test_an_unknown_policy_code_returns_the_code_itself():
    assert title_for("HC-PC-999") == "HC-PC-999"
