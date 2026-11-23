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

    lines = placement["lines_cleared"]
    return lines * 1000 - holes * 10 - max_h * 5
