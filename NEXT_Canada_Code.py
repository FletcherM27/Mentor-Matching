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
    rank_to_points = {0:5, 1:4, 2:3, 3:2, 4:1}
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
    rank_to_points = {0:5, 1:4, 2:3, 3:2, 4:1}
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

def build_bipartite_graph(
    expanded_mentor_prefs, slot_to_mentor,
    expanded_founder_prefs, slot_to_founder,
    overlap_bonus=2
):
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

            # If both are 0, no synergy => skip
            if mentor_points > 0 or founder_points > 0:
                total = mentor_points + founder_points
                # if both sides rank each other, add overlap bonus
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
    Reads the CSVs, runs the matching, returns the results as a list of strings.
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

    # 5. Interpret results, removing duplicates, building custom lines
    used_pairs = set()
    total_weight = 0.0
    result_lines = []
    result_lines.append("=== MAX-CARDINALITY MATCHING (DETAILED FORMAT) ===")

    for edge in matched_edges:
        nodeA, nodeB = list(edge)
        # figure out which is mentor vs founder
        if nodeA in expanded_mentor_prefs:
            ms, fs = nodeA, nodeB
        else:
            ms, fs = nodeB, nodeA

        mentor_name = slot_to_mentor[ms]
        founder_name = slot_to_founder[fs]

        # skip duplicates
        if (mentor_name, founder_name) in used_pairs:
            continue
        used_pairs.add((mentor_name, founder_name))

        # total synergy for this edge
        w = G[nodeA][nodeB]["weight"]
        total_weight += w

        # figure out each side's raw rank points
        mentor_points = expanded_mentor_prefs[ms].get(founder_name, 0)
        founder_points = expanded_founder_prefs[fs].get(mentor_name, 0)

        # build a line with "MentorName - FounderName - MentorName's X Choice - FounderName's Y Choice - Score=Z"
        line_str = (
            f"{mentor_name} - {founder_name}:  "
            f"  {mentor_name}'s {choice_label(mentor_points)} "
            f"{founder_name}'s {choice_label(founder_points)}: "
            f"  Score= {w} "
        )

        result_lines.append(line_str)

    # 6. Final summary lines
    result_lines.append(f"\nNumber of unique mentor–founder pairs: {len(used_pairs)}")
    result_lines.append(f"Total synergy across matched pairs: {total_weight}")

    return result_lines


# Optional: if you want to run it from the command line:
if __name__ == "__main__":
    # Example usage if you run 'python NEXT_Canada_Code.py'
    result = run_matching("Mentor Matching_Mentor Rankings-Grid view.csv",
                          "Mentor Matching_Founder Rankings-Grid view.csv")
    for line in result:
        print(line)
