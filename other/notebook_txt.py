from pathlib import Path
import nbformat

def ipynb_to_txt(ipynb_path, txt_path=None):
    """Export a Jupyter notebook to a reversible TXT representation."""
    ipynb_path = Path(ipynb_path)
    txt_path = Path(txt_path) if txt_path else ipynb_path.with_suffix(".txt")
    notebook = nbformat.read(ipynb_path, as_version=4)
    with txt_path.open("w", encoding="utf-8") as f:
        nbformat.write(notebook, f)
    return txt_path

def txt_to_ipynb(txt_path, ipynb_path=None):
    """Reconstruct a Jupyter notebook from its TXT representation."""
    txt_path = Path(txt_path)
    ipynb_path = (Path(ipynb_path) if ipynb_path else txt_path.with_suffix(".ipynb"))
    with txt_path.open("r", encoding="utf-8") as f:
        notebook = nbformat.read(f, as_version=4)
    nbformat.validate(notebook)
    nbformat.write(notebook, ipynb_path)
    return ipynb_path