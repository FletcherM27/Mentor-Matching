import streamlit as st
import pandas as pd  # We'll use pandas for CSV export
import NEXT_Canada_Code   # Must match the .py file name exactly

st.title("NEXT Canada Mentor Matching")

mentor_csv_file = st.file_uploader("Upload Mentor Rankings CSV", type=["csv"])
founder_csv_file = st.file_uploader("Upload Founder Rankings CSV", type=["csv"])

pairs_data = None  # We'll store the matched pairs data for CSV export

if mentor_csv_file and founder_csv_file:
    if st.button("Get Results"):
        import tempfile
        # Save uploaded files as temporary CSV files
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_mentor:
            tmp_mentor.write(mentor_csv_file.read())
            mentor_path = tmp_mentor.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_founder:
            tmp_founder.write(founder_csv_file.read())
            founder_path = tmp_founder.name

        # Run the matching function, which returns (result_lines, pairs_data)
        result_lines, pairs_data = NEXT_Canada_Code.run_matching(mentor_path, founder_path)

        st.write("**Results**")
        for line in result_lines:
            st.write(line)

if pairs_data is not None:
    # Display the download button once pairs_data is available
    df = pd.DataFrame(pairs_data)
    csv_str = df.to_csv(index=False)
    st.download_button(
        label="Download CSV",
        data=csv_str,
        file_name="mentor_matching_results.csv",
        mime="text/csv"
    )
