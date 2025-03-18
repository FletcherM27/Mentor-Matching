import csv
import networkx as nx

############################################################################
### 1. LOADING DATA
############################################################################

def load_mentor_data(mentor_csv):
    """
    CSV columns (example):
      0: Mentor Name
      1..5: top picks
      6: Mentor capacity (int)
    Returns:
      mentor_prefs = {mentorName: {founderName: points, ...}}
      mentor_caps  = {mentorName: capacity}
    """
    rank_to_points = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1}
    mentor_prefs = {}
    mentor_caps = {}

    with open(mentor_csv, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip header row
        for row in reader:
            if not row:
                continue
            mentor_name = row[0].strip()
            picks = row[1:6]
            capacity_str = row[6] if len(row) >= 7 else "1"

            try:
                capacity = int(float(capacity_str.strip()))
            except ValueError:
                capacity = 1

            prefs_dict = {}
            for i, pick in enumerate(picks):
                p = pick.strip()
                if p:
                    prefs_dict[p] = rank_to_points[i]

            mentor_prefs[mentor_name] = prefs_dict
            mentor_caps[mentor_name] = capacity

    return mentor_prefs, mentor_caps


def load_founder_data(founder_csv):
    """
    CSV columns (example):
      0: Founder Name
      1..5: top picks
    Returns:
      founder_prefs = {founderName: {mentorName: points, ...}}
    """
    rank_to_points = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1}
    founder_prefs = {}

    with open(founder_csv, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row:
                continue

            founder_name = row[0].strip()
            picks = row[1:6]

            prefs_dict = {}
            for i, pick in enumerate(picks):
                pick = pick.strip()
                if pick:
                    prefs_dict[pick] = rank_to_points[i]

            founder_prefs[founder_name] = prefs_dict

    return founder_prefs

############################################################################
### 2. EXPAND (REPLICATE) MENTORS & FOUNDERS BY CAPACITY
############################################################################

def expand_mentors_by_capacity(mentor_prefs, mentor_caps):
    """
    For each mentor M with capacity c, create c slots:
       M_slot1..M_slotc
    expanded_mentor_prefs[M_slot_i] = same preference dict as M
    slot_to_mentor[M_slot_i] = M
    """
    expanded_mentor_prefs = {}
    slot_to_mentor = {}

    for mentor_name, capacity in mentor_caps.items():
        for i in range(capacity):
            slot_name = f"{mentor_name}_slot{i+1}"
            expanded_mentor_prefs[slot_name] = mentor_prefs[mentor_name]
            slot_to_mentor[slot_name] = mentor_name

    return expanded_mentor_prefs, slot_to_mentor


def expand_founders_by_capacity(founder_prefs, founder_caps):
    """
    For each founder F with capacity c, create c slots:
       F_slot1..F_slotc
    expanded_founder_prefs[F_slot_i] = same preference dict as F
    slot_to_founder[F_slot_i] = F
    """
    expanded_founder_prefs = {}
    slot_to_founder = {}

    for founder_name, capacity in founder_caps.items():
        for i in range(capacity):
            slot_name = f"{founder_name}_slot{i+1}"
            expanded_founder_prefs[slot_name] = founder_prefs[founder_name]
            slot_to_founder[slot_name] = founder_name

    return expanded_founder_prefs, slot_to_founder

############################################################################
### 3. BUILD A BIPARTITE GRAPH & RUN MAX-WEIGHT MATCHING
############################################################################

def build_bipartite_graph(expanded_mentor_prefs, slot_to_mentor,
                          expanded_founder_prefs, slot_to_founder,
                          overlap_bonus=2):
    """
    Creates a bipartite Graph:
      - Left nodes = mentor slots
      - Right nodes = founder slots
      - Edge weight = (mentor_points + founder_points)
                     + overlap_bonus if both sides > 0
    """
    G = nx.Graph()

    mentor_slots = list(expanded_mentor_prefs.keys())
    founder_slots = list(expanded_founder_prefs.keys())

    G.add_nodes_from(mentor_slots, bipartite=0)
    G.add_nodes_from(founder_slots, bipartite=1)

    for ms in mentor_slots:
        for fs in founder_slots:
            mentor_name = slot_to_mentor[ms]
            founder_name = slot_to_founder[fs]

            mentor_points = expanded_mentor_prefs[ms].get(founder_name, 0)
            founder_points = expanded_founder_prefs[fs].get(mentor_name, 0)

            if mentor_points > 0 or founder_points > 0:
                total = mentor_points + founder_points
                if mentor_points > 0 and founder_points > 0:
                    total += overlap_bonus
                G.add_edge(ms, fs, weight=total)

    return G


def run_maximum_cardinality_max_weight(G):
    """
    Return the edges from nx.max_weight_matching(G, maxcardinality=True).
    Yields a set of frozensets({nodeA, nodeB}).
    """
    return nx.max_weight_matching(G, maxcardinality=True)

############################################################################
### 4. CHOICE LABEL HELPER
############################################################################

def choice_label(points):
    """
    Convert the 5-4-3-2-1 system into "First Choice", "Second Choice", etc.
    """
    if points == 5:
        return "First Choice"
    elif points == 4:
        return "Second Choice"
    elif points == 3:
        return "Third Choice"
    elif points == 2:
        return "Fourth Choice"
    elif points == 1:
        return "Fifth Choice"
    else:
        return "Unranked"

############################################################################
### 5. THE FUNCTION STREAMLIT WILL CALL
############################################################################

def run_matching(mentor_csv_path, founder_csv_path):
    """
    The function that Streamlit calls.
    Reads the CSVs, runs the matching, and returns two items:
      1) result_lines: multi-line text output for display.
      2) pairs_data:   a list of dicts for CSV export with the columns:
             Mentor Name, Venture Name, Mentor's Choice,
             Venture's Choice, Total Points
             (For Mentor's and Venture's Choice, we include the name in the text.)
    """

    # 1. Load data
    mentor_prefs, mentor_caps = load_mentor_data(mentor_csv_path)
    founder_prefs = load_founder_data(founder_csv_path)

    # 2. Suppose each founder can match 2 times
    founder_caps = {f: 2 for f in founder_prefs}

    # 3. Expand mentors & founders
    expanded_mentor_prefs, slot_to_mentor = expand_mentors_by_capacity(mentor_prefs, mentor_caps)
    expanded_founder_prefs, slot_to_founder = expand_founders_by_capacity(founder_prefs, founder_caps)

    # 4. Build bipartite graph and match
    overlap_bonus = 2
    G = build_bipartite_graph(expanded_mentor_prefs, slot_to_mentor,
                              expanded_founder_prefs, slot_to_founder,
                              overlap_bonus=overlap_bonus)

    matched_edges = run_maximum_cardinality_max_weight(G)

    used_pairs = set()
    total_weight = 0.0
    result_lines = []
    pairs_data = []  # for CSV export

    match_index = 1

    for edge in matched_edges:
        nodeA, nodeB = list(edge)
        # Determine which is mentor slot vs. founder slot
        if nodeA in expanded_mentor_prefs:
            ms, fs = nodeA, nodeB
        else:
            ms, fs = nodeB, nodeA

        mentor_name = slot_to_mentor[ms]
        founder_name = slot_to_founder[fs]

        if (mentor_name, founder_name) in used_pairs:
            continue
        used_pairs.add((mentor_name, founder_name))

        # Synergy (total points)
        w = G[nodeA][nodeB]["weight"]
        total_weight += w

        # Retrieve rank points for each side
        mentor_points = expanded_mentor_prefs[ms].get(founder_name, 0)
        founder_points = expanded_founder_prefs[fs].get(mentor_name, 0)

        # Build multi-line text output
        heading = f"Match {match_index}"
        line1 = f"{mentor_name} <----> {founder_name}"
        line2 = f"- {mentor_name}'s {choice_label(mentor_points)} and {founder_name}'s {choice_label(founder_points)}"
        line3 = f"- Total Points = {w}"

        result_lines.append(heading)
        result_lines.append(line1)
        result_lines.append(line2)
        result_lines.append(line3)
        result_lines.append("")  # blank line for spacing

        # Build CSV row (with extended text in columns C and D)
        pairs_data.append({
            "Mentor Name": mentor_name,
            "Venture Name": founder_name,
            "Mentor's Choice": f"{mentor_name}'s {choice_label(mentor_points)}",
            "Venture's Choice": f"{founder_name}'s {choice_label(founder_points)}",
            "Total Points": w
        })

        match_index += 1

    # Append summary lines to the multi-line output
    result_lines.append(f"Number of unique mentor–founder pairs: {len(used_pairs)}")
    result_lines.append(f"Total synergy across matched pairs: {total_weight}")

    # Build match count summaries for mentors and founders
    mentor_match_counts = {}
    founder_match_counts = {}

    for mentor, founder in used_pairs:
        mentor_match_counts[mentor] = mentor_match_counts.get(mentor, 0) + 1
        founder_match_counts[founder] = founder_match_counts.get(founder, 0) + 1

    result_lines.append("")
    result_lines.append("=== Mentor Matches ===")
    for mentor, count in mentor_match_counts.items():
        # mentor_caps holds the capacity for each mentor
        cap = mentor_caps.get(mentor, "?")
        result_lines.append(f"{mentor}: {count}/{cap} matches")

    result_lines.append("")
    result_lines.append("=== Founder Matches ===")
    for founder, count in founder_match_counts.items():
        # For founders we default to a capacity of 2
        result_lines.append(f"{founder}: {count}/2 matches")
    result_lines.append("")

    return result_lines, pairs_data


if __name__ == "__main__":
    test_output, test_data = run_matching("Mentor Matching_Mentor Rankings-Grid view.csv",
                                          "Mentor Matching_Founder Rankings-Grid view.csv")
    for line in test_output:
        print(line)
