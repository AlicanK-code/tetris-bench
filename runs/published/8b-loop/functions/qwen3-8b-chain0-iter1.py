def score(board, placement):
    # Calculate number of holes
    holes = 0
    for c in range(10):
        has_filled = False
        for r in range(20):
            if board[r][c]:
                has_filled = True
            else:
                if has_filled:
                    holes += 1

    # Calculate maximum column height
    max_h = 0
    for c in range(10):
        current_max = -1
        for r in range(20):
            if board[r][c]:
                current_max = r
        if current_max > max_h:
            max_h = current_max

    # Calculate average column height
    total_height = 0
    for c in range(10):
        current_height = 0
        for r in range(20):
            if board[r][c]:
                current_height = r
        total_height += current_height
    avg_h = total_height / 10

    lines = placement["lines_cleared"]
    # Weighted scoring formula to prioritize line clears, minimize holes, and reduce stack height
    return lines * 1000 - holes * 50 - max_h * 20 - avg_h * 15
