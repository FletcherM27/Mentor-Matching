import os
import tempfile
import streamlit as st
import pandas as pd

import NEXT_Canada_Code  # Keep this if your backend file is NEXT_Canada_Code.py
# If your file is revised_matching.py instead, use:
# import revised_matching as NEXT_Canada_Code


st.set_page_config(page_title="NEXT Canada Mentor Matching", layout="wide")
st.title("NEXT Canada Mentor Matching")

if "result_lines" not in st.session_state:
    st.session_state["result_lines"] = None

if "pairs_data" not in st.session_state:
    st.session_state["pairs_data"] = None

mentor_csv_file = st.file_uploader("Upload Mentor Rankings CSV", type=["csv"])
founder_csv_file = st.file_uploader("Upload Founder Rankings CSV", type=["csv"])

if mentor_csv_file and founder_csv_file:
    if st.button("Get Results", type="primary"):
        mentor_path = None
        founder_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_mentor:
                tmp_mentor.write(mentor_csv_file.getvalue())
                mentor_path = tmp_mentor.name

            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_founder:
                tmp_founder.write(founder_csv_file.getvalue())
                founder_path = tmp_founder.name

            with st.spinner("Running mentor matching..."):
                result_lines, pairs_data = NEXT_Canada_Code.run_matching(
                    mentor_path,
                    founder_path
                )

            st.session_state["result_lines"] = result_lines
            st.session_state["pairs_data"] = pairs_data

        except ValueError as e:
            st.session_state["result_lines"] = None
            st.session_state["pairs_data"] = None
            st.error(str(e))

        except Exception as e:
            st.session_state["result_lines"] = None
            st.session_state["pairs_data"] = None
            st.error(f"Something went wrong while running the matching algorithm: {e}")

        finally:
            for path in (mentor_path, founder_path):
                if path and os.path.exists(path):
                    os.unlink(path)

if st.session_state["result_lines"]:
    st.subheader("Results")
    st.text("\n".join(st.session_state["result_lines"]))

if st.session_state["pairs_data"]:
    df = pd.DataFrame(st.session_state["pairs_data"])

    st.subheader("Matched Pairs")
    st.dataframe(df, use_container_width=True, hide_index=True)

    csv_str = df.to_csv(index=False)
    st.download_button(
        label="Download CSV",
        data=csv_str,
        file_name="mentor_matching_results.csv",
        mime="text/csv"
    )
