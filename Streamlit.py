import streamlit as st
from io import StringIO
import NEXT_Canada_Code   # Must match the .py file name exactly

st.title("NEXT Canada Mentor Matching")

mentor_csv_file = st.file_uploader("Upload Mentor Rankings CSV", type=["csv"])
founder_csv_file = st.file_uploader("Upload Founder Rankings CSV", type=["csv"])

if mentor_csv_file and founder_csv_file:
    if st.button("Get Results"):
        # Convert files to temporary CSVs on disk
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_mentor:
            tmp_mentor.write(mentor_csv_file.read())
            mentor_path = tmp_mentor.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_founder:
            tmp_founder.write(founder_csv_file.read())
            founder_path = tmp_founder.name

        # Then call the run_matching function in NEXT_Canada_Code.py
        results = NEXT_Canada_Code.run_matching(mentor_path, founder_path)

        st.write("**Results**")
        for line in results:
            st.write(line)
