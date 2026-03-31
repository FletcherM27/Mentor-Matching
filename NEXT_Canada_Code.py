import csv
import networkx as nx


############################################################################
### 1. CONSTANTS / HELPERS
############################################################################

DEFAULT_FOUNDER_CAPACITY = 2
DEFAULT_OVERLAP_BONUS = 2
RANK_TO_POINTS = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1}
POINTS_TO_LABEL = {
    5: "First Choice",
    4: "Second Choice",
    3: "Third Choice",
    2: "Fourth Choice",
    1: "Fifth Choice",
}


def choice_label(points):
    return POINTS_TO_LABEL.get(points, "Unranked")


def top_choice_name(pref_dict):
    for name, points in pref_dict.items():
        if points == 5:
            return name
    return None


def build_pref_dict(picks, row_num, owner_name, owner_type):
    prefs_dict = {}
    seen = set()

    for i, raw_pick in enumerate(picks):
        pick = raw_pick.strip()
        if not pick:
            continue
        if pick in seen:
            raise ValueError(
                f"Duplicate pick '{pick}' found in {owner_type} '{owner_name}' on row {row_num}."
            )
        seen.add(pick)
        prefs_dict[pick] = RANK_TO_POINTS[i]

    return prefs_dict


############################################################################
### 2. LOADING DATA
############################################################################

def load_mentor_data(mentor_csv):
    mentor_prefs = {}
    mentor_caps = {}

    with open(mentor_csv, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header

        for row_num, row in enumerate(reader, start=2):
            if not row or not any(cell.strip() for cell in row):
                continue

            row = list(row)
            if len(row) < 7:
                row += [""] * (7 - len(row))

            mentor_name = row[0].strip()
            if not mentor_name:
                raise ValueError(f"Blank mentor name on row {row_num}.")
            if mentor_name in mentor_prefs:
                raise ValueError(f"Duplicate mentor name '{mentor_name}' on row {row_num}.")

            picks = row[1:6]
            capacity_str = row[6].strip()

            if not capacity_str:
                raise ValueError(
                    f"Missing mentor capacity for '{mentor_name}' on row {row_num}."
                )

            try:
                capacity = int(float(capacity_str))
            except ValueError as exc:
                raise ValueError(
                    f"Invalid mentor capacity '{capacity_str}' for '{mentor_name}' on row {row_num}."
                ) from exc

            if capacity < 0:
                raise ValueError(
                    f"Mentor capacity cannot be negative for '{mentor_name}' on row {row_num}."
                )

            mentor_prefs[mentor_name] = build_pref_dict(
                picks, row_num=row_num, owner_name=mentor_name, owner_type="mentor"
            )
            mentor_caps[mentor_name] = capacity

    return mentor_prefs, mentor_caps


def load_founder_data(founder_csv):
    founder_prefs = {}

    with open(founder_csv, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header

        for row_num, row in enumerate(reader, start=2):
            if not row or not any(cell.strip() for cell in row):
                continue

            row = list(row)
            if len(row) < 6:
                row += [""] * (6 - len(row))

            founder_name = row[0].strip()
            if not founder_name:
                raise ValueError(f"Blank founder name on row {row_num}.")
            if founder_name in founder_prefs:
                raise ValueError(f"Duplicate founder name '{founder_name}' on row {row_num}.")

            picks = row[1:6]

            founder_prefs[founder_name] = build_pref_dict(
                picks, row_num=row_num, owner_name=founder_name, owner_type="founder"
            )

    return founder_prefs


def validate_cross_references(mentor_prefs, founder_prefs):
    """
    Ignore rankings that reference mentors or ventures not present in the
    other file. Those names will be skipped automatically later because
    only mentors in mentor_caps and ventures in founder_caps can be matched.
    """
    return


############################################################################
### 3. SCORING
############################################################################

def get_pair_breakdown(mentor_name, founder_name, mentor_prefs, founder_prefs, overlap_bonus=DEFAULT_OVERLAP_BONUS):
    mentor_points = mentor_prefs.get(mentor_name, {}).get(founder_name, 0)
    founder_points = founder_prefs.get(founder_name, {}).get(mentor_name, 0)

    total_points = mentor_points + founder_points
    mutual_rank = mentor_points > 0 and founder_points > 0
    if mutual_rank:
        total_points += overlap_bonus

    return {
        "mentor_points": mentor_points,
        "founder_points": founder_points,
        "mutual_rank": mutual_rank,
        "total_points": total_points,
    }


def build_pair_scores(mentor_prefs, founder_prefs, overlap_bonus=DEFAULT_OVERLAP_BONUS):
    candidate_pairs = set()

    for mentor_name, prefs in mentor_prefs.items():
        for founder_name in prefs:
            candidate_pairs.add((mentor_name, founder_name))

    for founder_name, prefs in founder_prefs.items():
        for mentor_name in prefs:
            candidate_pairs.add((mentor_name, founder_name))

    pair_scores = {}
    for mentor_name, founder_name in sorted(candidate_pairs):
        breakdown = get_pair_breakdown(
            mentor_name, founder_name, mentor_prefs, founder_prefs, overlap_bonus=overlap_bonus
        )
        if breakdown["total_points"] > 0:
            pair_scores[(mentor_name, founder_name)] = breakdown["total_points"]

    return pair_scores


############################################################################
### 4. LOCK MUTUAL FIRST-CHOICE PAIRS
############################################################################

def lock_mutual_first_choice_pairs(mentor_prefs, founder_prefs, mentor_caps, founder_caps):
    remaining_mentor_caps = dict(mentor_caps)
    remaining_founder_caps = dict(founder_caps)
    locked_pairs = []

    for mentor_name in sorted(mentor_prefs):
        if remaining_mentor_caps.get(mentor_name, 0) <= 0:
            continue

        founder_name = top_choice_name(mentor_prefs[mentor_name])
        if not founder_name:
            continue
        if remaining_founder_caps.get(founder_name, 0) <= 0:
            continue

        founder_top_choice = top_choice_name(founder_prefs.get(founder_name, {}))
        if founder_top_choice == mentor_name:
            locked_pairs.append((mentor_name, founder_name))
            remaining_mentor_caps[mentor_name] -= 1
            remaining_founder_caps[founder_name] -= 1

    return locked_pairs, remaining_mentor_caps, remaining_founder_caps


############################################################################
### 5. MAX-CARDINALITY, THEN MAX-SCORE SOLVER
############################################################################

def build_capacity_graph(mentor_caps, founder_caps, pair_scores, excluded_pairs=None):
    excluded_pairs = excluded_pairs or set()

    G = nx.DiGraph()
    source = "__SOURCE__"
    sink = "__SINK__"

    G.add_node(source)
    G.add_node(sink)

    for mentor_name in sorted(mentor_caps):
        cap = mentor_caps[mentor_name]
        if cap > 0:
            G.add_edge(source, ("mentor", mentor_name), capacity=cap)

    for founder_name in sorted(founder_caps):
        cap = founder_caps[founder_name]
        if cap > 0:
            G.add_edge(("founder", founder_name), sink, capacity=cap)

    for (mentor_name, founder_name), score in sorted(pair_scores.items()):
        if score <= 0:
            continue
        if (mentor_name, founder_name) in excluded_pairs:
            continue
        if mentor_caps.get(mentor_name, 0) <= 0:
            continue
        if founder_caps.get(founder_name, 0) <= 0:
            continue

        G.add_edge(("mentor", mentor_name), ("founder", founder_name), capacity=1)

    return G, source, sink


def build_min_cost_graph(mentor_caps, founder_caps, pair_scores, required_flow, excluded_pairs=None):
    excluded_pairs = excluded_pairs or set()

    G = nx.DiGraph()
    source = "__SOURCE__"
    sink = "__SINK__"

    G.add_node(source, demand=-required_flow)
    G.add_node(sink, demand=required_flow)

    max_pair_score = max(pair_scores.values(), default=0)
    cost_shift = max_pair_score + 1

    for mentor_name in sorted(mentor_caps):
        cap = mentor_caps[mentor_name]
        if cap > 0:
            G.add_edge(source, ("mentor", mentor_name), capacity=cap, weight=0)

    for founder_name in sorted(founder_caps):
        cap = founder_caps[founder_name]
        if cap > 0:
            G.add_edge(("founder", founder_name), sink, capacity=cap, weight=0)

    for (mentor_name, founder_name), score in sorted(pair_scores.items()):
        if score <= 0:
            continue
        if (mentor_name, founder_name) in excluded_pairs:
            continue
        if mentor_caps.get(mentor_name, 0) <= 0:
            continue
        if founder_caps.get(founder_name, 0) <= 0:
            continue

        G.add_edge(
            ("mentor", mentor_name),
            ("founder", founder_name),
            capacity=1,
            weight=cost_shift - score,
        )

    return G


def solve_remaining_pairs(mentor_caps, founder_caps, pair_scores, excluded_pairs=None):
    excluded_pairs = excluded_pairs or set()

    capacity_graph, source, sink = build_capacity_graph(
        mentor_caps, founder_caps, pair_scores, excluded_pairs=excluded_pairs
    )
    max_cardinality = nx.maximum_flow_value(capacity_graph, source, sink)

    if max_cardinality == 0:
        return []

    min_cost_graph = build_min_cost_graph(
        mentor_caps,
        founder_caps,
        pair_scores,
        required_flow=max_cardinality,
        excluded_pairs=excluded_pairs,
    )
    _, flow_dict = nx.network_simplex(min_cost_graph)

    selected_pairs = []
    for mentor_name in sorted(mentor_caps):
        mentor_node = ("mentor", mentor_name)
        if mentor_node not in flow_dict:
            continue

        for neighbor, flow in flow_dict[mentor_node].items():
            if flow != 1:
                continue
            if isinstance(neighbor, tuple) and len(neighbor) == 2 and neighbor[0] == "founder":
                founder_name = neighbor[1]
                selected_pairs.append((mentor_name, founder_name))

    return sorted(selected_pairs)


############################################################################
### 6. MAIN FUNCTION STREAMLIT WILL CALL
############################################################################

def run_matching(
    mentor_csv_path,
    founder_csv_path,
    founder_capacity=DEFAULT_FOUNDER_CAPACITY,
    overlap_bonus=DEFAULT_OVERLAP_BONUS,
):
    mentor_prefs, mentor_caps = load_mentor_data(mentor_csv_path)
    founder_prefs = load_founder_data(founder_csv_path)

    validate_cross_references(mentor_prefs, founder_prefs)

    founder_caps = {founder_name: founder_capacity for founder_name in founder_prefs}

    locked_pairs, remaining_mentor_caps, remaining_founder_caps = lock_mutual_first_choice_pairs(
        mentor_prefs, founder_prefs, mentor_caps, founder_caps
    )

    pair_scores = build_pair_scores(
        mentor_prefs, founder_prefs, overlap_bonus=overlap_bonus
    )

    locked_set = set(locked_pairs)

    remaining_pairs = solve_remaining_pairs(
        remaining_mentor_caps,
        remaining_founder_caps,
        pair_scores,
        excluded_pairs=locked_set,
    )

    final_pairs = locked_pairs + remaining_pairs

    pair_records = []
    for mentor_name, founder_name in final_pairs:
        breakdown = get_pair_breakdown(
            mentor_name, founder_name, mentor_prefs, founder_prefs, overlap_bonus=overlap_bonus
        )
        pair_records.append({
            "mentor_name": mentor_name,
            "founder_name": founder_name,
            "mentor_points": breakdown["mentor_points"],
            "founder_points": breakdown["founder_points"],
            "total_points": breakdown["total_points"],
            "locked": (mentor_name, founder_name) in locked_set,
        })

    pair_records.sort(
        key=lambda r: (
            0 if r["locked"] else 1,
            -r["total_points"],
            r["mentor_name"].lower(),
            r["founder_name"].lower(),
        )
    )

    total_weight = sum(record["total_points"] for record in pair_records)

    result_lines = []
    pairs_data = []

    if locked_pairs:
        result_lines.append("=== Locked Mutual First-Choice Matches ===")
        result_lines.append("These pairs were matched automatically before optimization.")
        result_lines.append("")

    for idx, record in enumerate(pair_records, start=1):
        mentor_name = record["mentor_name"]
        founder_name = record["founder_name"]
        mentor_points = record["mentor_points"]
        founder_points = record["founder_points"]
        total_points = record["total_points"]

        result_lines.append(f"Match {idx}")
        result_lines.append(f"{mentor_name} <----> {founder_name}")

        if record["locked"]:
            result_lines.append("- Locked because both ranked each other First Choice")

        result_lines.append(
            f"- {mentor_name}'s {choice_label(mentor_points)} and {founder_name}'s {choice_label(founder_points)}"
        )
        result_lines.append(f"- Total Points = {total_points}")
        result_lines.append("")

        pairs_data.append({
            "Mentor Name": mentor_name,
            "Venture Name": founder_name,
            "Mentor's Choice": f"{mentor_name}'s {choice_label(mentor_points)}",
            "Venture's Choice": f"{founder_name}'s {choice_label(founder_points)}",
            "Total Points": total_points,
        })

    result_lines.append(f"Number of unique mentor–founder pairs: {len(pair_records)}")
    result_lines.append(f"Total synergy across matched pairs: {total_weight}")

    mentor_match_counts = {mentor_name: 0 for mentor_name in mentor_prefs}
    founder_match_counts = {founder_name: 0 for founder_name in founder_prefs}

    for record in pair_records:
        mentor_match_counts[record["mentor_name"]] += 1
        founder_match_counts[record["founder_name"]] += 1

    result_lines.append("")
    result_lines.append("=== Mentor Matches ===")
    for mentor_name in sorted(mentor_match_counts):
        cap = mentor_caps[mentor_name]
        count = mentor_match_counts[mentor_name]
        result_lines.append(f"{mentor_name}: {count}/{cap} matches")

    result_lines.append("")
    result_lines.append("=== Founder Matches ===")
    for founder_name in sorted(founder_match_counts):
        cap = founder_caps[founder_name]
        count = founder_match_counts[founder_name]
        result_lines.append(f"{founder_name}: {count}/{cap} matches")

    unmatched_mentors = [m for m, count in sorted(mentor_match_counts.items()) if count == 0]
    unmatched_founders = [f for f, count in sorted(founder_match_counts.items()) if count == 0]

    result_lines.append("")
    result_lines.append("=== Unmatched Mentors ===")
    result_lines.extend(unmatched_mentors or ["None"])

    result_lines.append("")
    result_lines.append("=== Unmatched Founders ===")
    result_lines.extend(unmatched_founders or ["None"])
    result_lines.append("")

    return result_lines, pairs_data


if __name__ == "__main__":
    test_output, test_data = run_matching(
        "Mentor Matching_Mentor Rankings-Grid view.csv",
        "Mentor Matching_Founder Rankings-Grid view.csv",
    )
    for line in test_output:
        print(line)
