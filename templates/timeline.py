import matplotlib.pyplot as plt

# Each event is a tuple: (label, numeric year, time string)
# The label is a multi-line string containing Phase header and title.
events = [
    # Phase 0
    (
        "Phase 0 - Already Done\n"
        "Angry Birds Reloaded - Space levels/characters/mechanics (2024-2025)\n",
        2024.5,
        "2024-2025"
    ),
    # Phase 1 - Classic Space content using existing games
    (
        "Phase 1 - Classic Space content using existing games\n"
        "Angry Birds Friends - Space Tournament(s) (Q2 2025 - )\n",
        2025.5,
        "Q2 2025 -"
    ),
    (
        "Phase 1 - Classic Space content using existing games\n"
        "ABBA - Space Biome (Q4 2025 - )\n",
        2025.9,
        "Q4 2025 -"
    ),
    (
        "Phase 1 - Classic Space content using existing games\n"
        "Angry Birds Dream about Space (2025-2026)\n",
        2025.75,
        "2025-2026"
    ),
    (
        "Phase 1 - Classic Space content using existing games\n"
        "Angry Birds Space included in Trilogy on Switch (Q1-Q2 2026)\n",
        2026.25,
        "Q1-Q2 2026"
    ),
    # Phase 2 - Investing in Classic Space content to build hype and relevancy
    (
        "Phase 2 - Investing in Classic Space content to build hype and relevancy\n"
        "Angry Birds Space - short form videos (Q3 2026?)\n",
        2026.75,
        "Q3 2026?"
    ),
    (
        "Phase 2 - Investing in Classic Space content to build hype and relevancy\n"
        "Classic Space merch (TBD)\n",
        2026.75,
        "TBD"
    ),
    (
        "Phase 2 - Investing in Classic Space content to build hype and relevancy\n"
        "AB Space enhanced for Apple Arcade or Netflix (2026?)\n",
        2026.75,
        "2026?"
    ),
    (
        "Phase 2 - Investing in Classic Space content to build hype and relevancy\n"
        "Space narrative in Project Purple (Q4 2026)\n",
        2026.9,
        "Q4 2026"
    ),
    (
        "Phase 2 - Investing in Classic Space content to build hype and relevancy\n"
        "Space in Angry Birds Luck Battle (Q4 2026)\n",
        2026.9,
        "Q4 2026"
    ),
    # Phase 3 - Movie-Style Space content introduced
    (
        "Phase 3 - Movie-Style Space content introduced.\n"
        "Angry Birds Movie 3 - Cliffhanger Ending (Q1 2027)\n",
        2027.25,
        "Q1 2027"
    ),
    (
        "Phase 3 - Movie-Style Space content introduced.\n"
        "Movie space merch (Q1 2027)\n",
        2027.25,
        "Q1 2027"
    ),
    (
        "Phase 3 - Movie-Style Space content introduced.\n"
        "Movie-Space themed event in Rumble (Q1 2027)\n",
        2027.25,
        "Q1 2027"
    ),
    (
        "Phase 3 - Movie-Style Space content introduced.\n"
        "NASA (Artemis III) or Firefly Aerospace (Blue Ghost II) collaboration on the moon (2026-2028)\n",
        2027.0,
        "2026-2028"
    ),
    # Phase 4 - Riding Space hype with significant investments
    (
        "Phase 4 - Riding Space hype with significant investments\n"
        "Movie Space themed long form developed w/ DNEG (2028?)\n",
        2028,
        "2028?"
    ),
    (
        "Phase 4 - Riding Space hype with significant investments\n"
        "Angry Birds Space 2 (2028?)\n",
        2028,
        "2028?"
    ),
    (
        "Phase 4 - Riding Space hype with significant investments\n"
        "Space themed Movie 4 (animation or hybrid) (2029 earliest)\n",
        2029,
        "2029 earliest"
    )
]

# Overall timeline range
start_year = 2024
end_year = 2030

fig, ax = plt.subplots(figsize=(14, 12))
ax.set_xlim(start_year, end_year)
ax.set_ylim(-1, len(events))
ax.set_xlabel("Year", fontsize=12)
ax.set_title("Angry Birds Space - Roadmap to 'the moon' Timeline", fontsize=16, fontweight='bold')

# Create alternating background colors for each year span
year_colors = ["#f0f8ff", "#e6f2ff"]  # Two light blue hues
for year in range(start_year, end_year):
    color = year_colors[(year - start_year) % len(year_colors)]
    ax.axvspan(year, year + 1, color=color, alpha=0.3)

# Plot each event with a marker and annotate with event details
for i, (label, year, time_str) in enumerate(events):
    # Draw vertical marker line with circle marker
    ax.plot([year, year], [i - 0.3, i + 0.3], marker="o", color="tab:blue", markersize=8)
    
    # Process the first line to bold only the "Phase X" portion.
    lines = label.split("\n")
    first_line = lines[0]
    if first_line.startswith("Phase"):
        if " - " in first_line:
            phase_part, remainder = first_line.split(" - ", 1)
            phase_part_bold = r"$\mathbf{" + phase_part + "}$"
            formatted_first_line = phase_part_bold + " - " + remainder
        else:
            formatted_first_line = r"$\mathbf{" + first_line + "}$"
    else:
        formatted_first_line = first_line
    
    # Reassemble the full label with formatted first line
    full_label = formatted_first_line
    if len(lines) > 1:
        full_label += "\n" + "\n".join(lines[1:])
    
    # Annotate text next to the marker with a slight offset
    ax.text(year + 0.05, i, f"{full_label}\n({time_str})", va="center", fontsize=10)

# Remove y-axis ticks and add x-axis gridlines
ax.set_yticks([])
ax.grid(axis="x", linestyle="--", alpha=0.5)

plt.tight_layout()
plt.show()