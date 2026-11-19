"""Generate original public-domain-style fixtures and verify both CLI routes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "pdf_workflow.py"


def run(*args, success=True):
    result = subprocess.run([sys.executable, str(CLI), *map(str, args)],
                            capture_output=True, text=True)
    if success and result.returncode:
        raise AssertionError(result.stderr)
    if not success and not result.returncode:
        raise AssertionError("Expected rejection.")
    return result


def main():
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        source = work / "source.pdf"
        doc = fitz.open()
        page = doc.new_page(width=720, height=405)
        page.insert_text((50, 70), "Original synthetic brand case", fontsize=20)
        page.draw_rect(fitz.Rect(50, 110, 250, 190), color=(0.2, 0.4, 0.6))
        page.add_stamp_annot(fitz.Rect(420, 220, 650, 330))
        ad = doc.new_page(width=720, height=405)
        ad.insert_text((40, 80), "Synthetic third-party membership advertisement", fontsize=18)
        last = doc.new_page(width=720, height=405)
        last.insert_text((50, 70), "Final content page", fontsize=20)
        doc.save(source)
        fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
        run("inspect", source, work / "inspect")
        inspection = json.loads((work / "inspect" / "inspection.json").read_text())
        plan = {
            "source_sha256": fingerprint,
            "delete_pages": [2],
            "annotations": [{
                "page": 1,
                "xrefs": [row["xref"] for row in inspection["pages"][0]["annotations"]],
            }],
        }
        plan_file = work / "plan.json"
        plan_file.write_text(json.dumps(plan))
        run("clean", source, work / "clean", "--plan", plan_file)
        cleaned = fitz.open(work / "clean" / "clean.pdf")
        assert len(cleaned) == 2
        assert not cleaned[0].annot_xrefs()
        assert "Final content page" in cleaned[1].get_text()
        checks = json.loads((work / "clean" / "verification.json").read_text())
        assert all(all(row[key] for key in [
            "size_equal", "font_payloads_equal", "image_payloads_equal", "page_content_equal",
        ]) for row in checks["checks"])
        assert hashlib.sha256(source.read_bytes()).hexdigest() == fingerprint
        run("clean", source, work / "clean", "--plan", plan_file, success=False)
        plan["source_sha256"] = "0" * 64
        plan_file.write_text(json.dumps(plan))
        run("clean", source, work / "wrong-input", "--plan", plan_file, success=False)
        font_map = work / "fonts.json"
        font_map.write_text(json.dumps({"Helvetica": "Arial"}))
        run("prepare-ppt", work / "clean" / "clean.pdf", work / "ppt",
            "--font-map", font_map)
        manifest = work / "ppt" / "ppt-manifest.json"
        data = json.loads(manifest.read_text())
        assert len(data["pages"]) == 2
        assert data["pages"][0]["text"][0]["text"] == "Original synthetic brand case"
        output = work / "editable.pptx"
        subprocess.run([os.environ.get("NODE", "node"), str(ROOT / "scripts" / "build_ppt.cjs"),
                        str(manifest), str(output)], check=True)
        with zipfile.ZipFile(output) as package:
            assert package.testzip() is None
            first = package.read("ppt/slides/slide1.xml").decode()
            assert "Original synthetic brand case" in first
            assert "Arial" in first
            assert len([name for name in package.namelist()
                        if name.startswith("ppt/slides/slide") and name.endswith(".xml")]) == 2
        print(json.dumps({
            "result": "pass",
            "checks": ["CLI inspect", "source fingerprint", "whole-page removal",
                       "annotation removal", "source preservation", "PDF retained payloads",
                       "overwrite rejection", "wrong-input rejection",
                       "editable text extraction", "PPTX structure and native text"],
            "untested": ["real PowerPoint edit/reopen", "OCR", "automatic ad classification",
                         "font identity", "font embedding", "Windows and Linux visual rendering"],
        }, indent=2))


if __name__ == "__main__":
    main()
