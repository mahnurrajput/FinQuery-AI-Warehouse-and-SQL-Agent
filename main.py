"""
main.py — Root-level Streamlit entrypoint.

Exists only to avoid a module-name collision between the `app/`
package and Streamlit's own `app.py` entry-script naming. Run this
file with `streamlit run main.py`; it delegates everything to
app/app.py.
"""

import runpy

runpy.run_path("app/app.py", run_name="__main__")