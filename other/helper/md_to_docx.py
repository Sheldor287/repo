from pathlib import Path
import pypandoc
from sympy import python


def md_to_docx(input_file, output_file=None):
    """
    Convert a Markdown file to a DOCX file.

    Parameters
    ----------
    input_file : str or Path
        Path to the Markdown file.
    output_file : str or Path, optional
        Output DOCX path. If omitted, uses the same filename with .docx.
    """
    input_file = Path(input_file)

    if not input_file.exists():
        raise FileNotFoundError(f"Markdown file not found: {input_file}")

    if output_file is None:
        output_file = input_file.with_suffix(".docx")
    else:
        output_file = Path(output_file)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    pypandoc.convert_file(
        str(input_file),
        to="docx",
        outputfile=str(output_file),
    )

    return output_file

# usage:    python md_to_docx.py document.md --> document.docx
# or:       python md_to_docx.py document.md -o output.docx

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert a Markdown file to DOCX.")
    parser.add_argument("input", help="Path to the Markdown file",)
    parser.add_argument("-o", "--output", help="Path to the output DOCX file",)
    args = parser.parse_args()
    output = md_to_docx(args.input, args.output)
    print(f"Converted:")
    print(f"  Markdown: {args.input}")
    print(f"  DOCX:     {output}")