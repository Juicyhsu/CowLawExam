# -*- coding: utf-8 -*-
import gzip
import shutil
from pathlib import Path

SRC_DIR = Path(r"c:\Users\user\Desktop\國考\網站")
DST_DIR = Path(r"c:\Users\user\Desktop\國考\部署")

def copy_and_compress():
    # Files/Dirs to copy
    copy_targets = [
        ("app.py", False),
        ("index.html", False),
        ("Procfile", False),
        ("requirements.txt", False),
        ("css", True),
        ("js", True),
    ]

    for name, is_dir in copy_targets:
        src = SRC_DIR / name
        dst = DST_DIR / name
        if is_dir:
            # If directory, clear dst and copy
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"Copied directory: {name}")
        else:
            shutil.copy2(src, dst)
            print(f"Copied file: {name}")

    # Gzip compress major JS files in both source and destination
    js_files_to_compress = [
        "explanations_data.js",
        "generated_flashcards.js",
        "audio_scripts.js",
        "questions_data.js"
    ]

    for dir_path in [SRC_DIR / "js", DST_DIR / "js"]:
        for js_name in js_files_to_compress:
            js_file = dir_path / js_name
            if js_file.exists():
                gz_file = dir_path / (js_name + ".gz")
                # Read original, write to gz
                with open(js_file, "rb") as f_in:
                    with gzip.open(gz_file, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                print(f"Compressed {js_file.relative_to(SRC_DIR.parent)} -> {gz_file.name}")

if __name__ == "__main__":
    copy_and_compress()
    print("Deployment preparation and gzip compression completed successfully!")
