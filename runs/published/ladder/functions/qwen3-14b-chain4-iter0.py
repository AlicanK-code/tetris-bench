def score(board, placement):
    # Count holes: empty cells with filled cells below
    holes = 0
    for row in range(20):
        for col in range(10):
            if not board[row][col]:
                # Check if there's any filled cell below
                has_filled_below = False
                for r in range(row + 1, 20):
                    if board[r][col]:
                        has_filled_below = True
                        break
                if has_filled_below:
                    holes += 1

    # Compute surface roughness: sum of absolute differences between adjacent column heights
    max_rows = []
    for col in range(10):
        max_row = -1
        for row in range(20):
            if board[row][col]:
                max_row = row
        max_rows.append(max_row)
    roughness = 0
    for i in range(9):
        roughness += abs(max_rows[i] - max_rows[i + 1])

    # Get lines cleared from placement
    lines_cleared = placement["lines_cleared"]

    # Combine into score: prioritize lines cleared, penalize holes and roughness
    return float(lines_cleared * 100 - holes * 5 - roughness * 2)
