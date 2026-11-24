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

    # Calculate maximum column height (with empty columns as 0)
    max_h = 0
    for c in range(10):
        current_max = -1
        for r in range(20):
            if board[r][c]:
                current_max = r
        if current_max == -1:
            current_max = 0
        if current_max > max_h:
            max_h = current_max

    # Calculate average column height (last filled row index)
    total_height = 0
    for c in range(10):
        current_height = 0
        for r in range(20):
            if board[r][c]:
                current_height = r
        total_height += current_height
    avg_h = total_height / 10

    # Weighted scoring formula with emphasis on holes and column heights
    lines = placement["lines_cleared"]
    return lines * 1000 - holes * 100 - max_h * 30 - avg_h * 20
