"""Regression: footer and inline promotions must not survive object-only cleanup."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "pdf_workflow.py"


def execute(source, output, plan):
    return subprocess.run(
        [sys.executable, str(CLI), "clean", str(source), str(output), "--plan", str(plan)],
        capture_output=True, text=True,
    )


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "source.pdf"
        doc = fitz.open()
        first = doc.new_page(width=720, height=405)
        first.insert_text((50, 70), "Retained brand content", fontsize=20)
        first.draw_rect(fitz.Rect(40, 110, 280, 210), color=(0.2, 0.4, 0.6))
        pixel = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), False)
        pixel.clear_with(170)
        first.insert_image(fitz.Rect(350, 120, 420, 190), pixmap=pixel)
        first.insert_text((30, 380), "Members only", fontsize=8)
        ad = doc.new_page(width=720, height=405)
        ad.insert_text((30, 70), "Unrelated advertising")
        last = doc.new_page(width=720, height=405)
        last.insert_text((50, 70), "Retained final page", fontsize=20)
        last.insert_text((50, 180), "Join our group", fontsize=12)
        doc.save(source)
        fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
        inspected = subprocess.run(
            [sys.executable, str(CLI), "inspect", str(source), str(root / "inspection")],
            capture_output=True, text=True,
        )
        assert inspected.returncode == 0, inspected.stderr
        inspection = json.loads((root / "inspection" / "inspection.json").read_text())
        assert {page["page"] for page in inspection["pages"] if page["text_candidates"]} == {1, 3}
        plan = {"source_sha256": fingerprint, "delete_pages": [2]}
        plan_file = root / "plan.json"
        plan_file.write_text(json.dumps(plan))

        result = execute(source, root / "incomplete", plan_file)
        assert result.returncode == 2, result.stderr
        incomplete = json.loads((root / "incomplete" / "verification.json").read_text())
        assert incomplete["cleanup_status"] == "needs_review"
        assert {row["original_page"] for row in incomplete["residual_text_candidates"]} == {1, 3}
        assert "NEEDS REVIEW" in (root / "incomplete" / "report.html").read_text()

        plan["text_removals"] = [
            {"pages": [1], "text": "Members only", "expected_rectangles_per_page": 1,
             "clip": [0, 350, 720, 405]},
            {"pages": [3], "text": "Join our group", "expected_rectangles_per_page": 1},
        ]
        plan_file.write_text(json.dumps(plan))
        result = execute(source, root / "complete", plan_file)
        assert result.returncode == 0, result.stderr
        report = json.loads((root / "complete" / "verification.json").read_text())
        assert report["cleanup_status"] == "text_scan_clear"
        assert report["residual_text_candidates"] == []
        assert all(row["font_payloads_equal"] and row["image_payloads_equal"]
                   and row["size_equal"] for row in report["checks"])
        cleaned = fitz.open(root / "complete" / "clean.pdf")
        assert len(cleaned) == 2
        assert "Retained brand content" in cleaned[0].get_text()
        assert "Retained final page" in cleaned[1].get_text()
        assert "Members only" not in cleaned[0].get_text()
        assert "Join our group" not in cleaned[1].get_text()
        original = fitz.open(source)
        clip = fitz.Rect(20, 20, 450, 250)
        assert original[0].get_pixmap(clip=clip).samples == cleaned[0].get_pixmap(clip=clip).samples
        assert hashlib.sha256(source.read_bytes()).hexdigest() == fingerprint

        plan["text_removals"][0]["expected_rectangles_per_page"] = 2
        plan_file.write_text(json.dumps(plan))
        result = execute(source, root / "wrong-count", plan_file)
        assert result.returncode != 0
        assert not (root / "wrong-count" / "clean.pdf").exists()
        print(json.dumps({
            "result": "pass",
            "checks": ["residual text triggers exit 2 and HTML warning",
                       "footer text removed", "inline promotion removed",
                       "original page mapping after deletion", "retained brand text",
                       "retained fonts and image bytes", "retained vector and image rendering",
                       "source hash unchanged", "expected match count rejection"],
        }, indent=2))


if __name__ == "__main__":
    main()
