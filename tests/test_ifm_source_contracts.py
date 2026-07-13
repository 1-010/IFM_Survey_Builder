import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _literal_assignment(source: str, name: str):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"assignment not found: {name}")


def test_admin_authentication_has_no_known_password_fallbacks():
    active_files = [
        ROOT / "ifm_dashboard.py",
        ROOT / "autodesk_assessment.py",
        ROOT / "autodesk_super_admin.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in active_files)
    assert "ifm-sales" not in combined
    assert "ifm-super-admin" not in combined


def test_customer_urls_are_not_sent_to_external_qr_service():
    source = (ROOT / "autodesk_assessment.py").read_text(encoding="utf-8")
    assert "api.qrserver.com" not in source
    assert "qrcode.make(prod_url)" in source


def test_default_ifm_questions_all_have_local_images():
    payload = json.loads((ROOT / "data" / "ifm_questions.json").read_text(encoding="utf-8"))
    source = (ROOT / "autodesk_assessment.py").read_text(encoding="utf-8")
    mapping = _literal_assignment(source, "IMAGE_MAPPING")
    question_ids = {question["question_id"] for question in payload["questions"]}
    assert question_ids <= set(mapping)
    missing_files = [name for name in mapping.values() if not (ROOT / "data" / "images" / name).exists()]
    assert missing_files == []


def test_portal_deep_links_are_routed_to_the_requested_tab():
    source = (ROOT / "autodesk_assessment.py").read_text(encoding="utf-8")
    assert 'requested_tab == "admin"' in source
    assert 'requested_tab == "dashboard"' in source
