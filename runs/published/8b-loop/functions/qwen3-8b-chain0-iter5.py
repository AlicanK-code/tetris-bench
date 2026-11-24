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

    # Calculate column heights
    column_heights = []
    for c in range(10):
        height = 0
        for r in range(19, -1, -1):
            if board[r][c]:
                height += 1
            else:
                break
        column_heights.append(height)

    max_h = max(column_heights)
    min_h = min(column_heights)
    surface_unevenness = max_h - min_h

    lines = placement["lines_cleared"]
    return lines * 100 - holes * 10 - max_h * 5 - surface_unevenness * 5
