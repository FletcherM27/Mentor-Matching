import streamlit as st
from io import StringIO
import pandas as pd  # We'll need pandas for CSV export
import NEXT_Canada_Code   # Must match the .py file name exactly

st.title("NEXT Canada Mentor Matching")

mentor_csv_file = st.file_uploader("Upload Mentor Rankings CSV", type=["csv"])
founder_csv_file = st.file_uploader("Upload Founder Rankings CSV", type=["csv"])

# We'll store pairs_data in a variable so we can export it
pairs_data = None

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

        # run_matching now returns (lines, data)
        result_lines, pairs_data = NEXT_Canada_Code.run_matching(mentor_path, founder_path)

        st.write("**Results**")
        for line in result_lines:
            st.write(line)

# If we have pairs_data, let the user export it as CSV
if pairs_data is not None:
    # We'll create a second button, or you can skip the button
    # and display the download right away.
    if st.button("Export CSV"):
        df = pd.DataFrame(pairs_data)
        csv_str = df.to_csv(index=False)
        st.download_button(
            label="Download Matches as CSV",
            data=csv_str,
            file_name="mentor_matching_results.csv",
            mime="text/csv"
        )
